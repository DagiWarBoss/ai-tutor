# backend/main.py

import os
import psycopg2
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from together import Together
from sentence_transformers import SentenceTransformer

# --- Explicitly load the .env file ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Securely load API Keys & DB Credentials ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- Initialize Models ---
llm_client = Together(api_key=TOGETHER_API_KEY)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# --- Pydantic Model for Request Body Validation ---
class ContentRequest(BaseModel):
    topic: str
    mode: str

app = FastAPI()

# --- CORS Configuration ---
origins = ["http://localhost", "http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Connection Function ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"CRITICAL: Could not connect to the database. Error: {e}")
        return None

# --- Helper function to parse flawed JSON from the AI ---
def parse_quiz_json_from_string(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("DEBUG: AI did not return valid JSON. Attempting regex parsing...")
        try:
            question_match = re.search(r'"question":\s*"(.*?)"', text, re.DOTALL)
            options_match = re.search(r'"options":\s*\{(.*?)\}', text, re.DOTALL)
            answer_match = re.search(r'"correct_answer":\s*"(.*?)"', text, re.DOTALL)
            explanation_match = re.search(r'"explanation":\s*"(.*?)"', text, re.DOTALL)

            if not all([question_match, options_match, answer_match, explanation_match]):
                return None

            question = question_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')
            options_str = options_match.group(1)
            correct_answer = answer_match.group(1).strip()
            explanation = explanation_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')

            options = {}
            option_matches = re.findall(r'"([A-D])":\s*"(.*?)"', options_str)
            for key, value in option_matches:
                options[key] = value.strip().replace('\\n', '\n').replace('\\"', '"')
            
            if len(options) != 4: return None

            return {"question": question, "options": options, "correct_answer": correct_answer, "explanation": explanation}
        except Exception:
            return None

# === ENDPOINT 1: Fetch the entire syllabus structure ===
@app.get("/api/syllabus")
async def get_syllabus():
    # ... (This function is unchanged)
    conn = None
    try:
        conn = get_db_connection()
        if conn is None: raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM subjects ORDER BY name")
            subjects_raw = cur.fetchall()
            cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number, chapter_number")
            chapters_raw = cur.fetchall()
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
            topics_raw = cur.fetchall()
            chapters_map = {c_id: {"id": c_id, "name": c_name, "number": c_num, "class_level": c_level, "topics": []} for c_id, c_name, c_num, s_id, c_level in chapters_raw}
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map: chapters_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})
            subjects_map = {s_id: {"id": s_id, "name": s_name, "chapters": []} for s_id, s_name in subjects_raw}
            for c_id, c_name, c_num, s_id, c_level in chapters_raw:
                if s_id in subjects_map: subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            syllabus = list(subjects_map.values())
        return JSONResponse(content=syllabus)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        if conn: conn.close()

# === ENDPOINT 2: The Multi-Purpose Content Generator ===
@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    topic_prompt = request.topic
    mode = request.mode
    conn = None
    try:
        topic_embedding = embedding_model.encode(topic_prompt).tolist()
        conn = get_db_connection()
        if conn is None: raise HTTPException(status_code=503, detail="Database connection unavailable.")
        relevant_text, context_level, context_name = "", "", ""
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            if not match_result: raise HTTPException(status_code=404, detail=f"Could not find a relevant topic for '{topic_prompt}'.")
            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = match_result
            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()
            if topic_text_result and topic_text_result[0] and topic_text_result[0].strip():
                relevant_text, context_level, context_name = topic_text_result[0], "Topic", matched_topic_name
            else:
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                if chapter_text_result and chapter_text_result[1] and chapter_text_result[1].strip():
                    relevant_text, context_level, context_name = chapter_text_result[1], "Chapter", chapter_text_result[0]
                else:
                    raise HTTPException(status_code=404, detail=f"Sorry, content for '{matched_topic_name}' and its parent chapter is unavailable.")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred while retrieving data.")
    finally:
        if conn: conn.close()

    max_chars = 15000
    if len(relevant_text) > max_chars: relevant_text = relevant_text[:max_chars]

    user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
    response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4}
    system_message = ""

    if mode == 'revise':
        system_message = """You are an AI assistant creating a structured 'cheat sheet' for a student preparing for the JEE exam..."""
    elif mode == 'practice':
        system_message = """
        You are an expert AI quiz generator for the JEE exam. Your task is to create one multiple-choice question (MCQ) based ONLY on the provided context.
        **CRITICAL INSTRUCTIONS:**
        1.  The question MUST be strictly relevant to the provided context.
        2.  If the context is purely theoretical, definitional, or insufficient to create a meaningful question, you MUST refuse by following the "EXAMPLE OF HOW TO REFUSE" format below.
        3.  Your entire response MUST be a single, valid JSON object.
        4.  The JSON object must have EXACTLY these keys: "question", "options", "correct_answer", "explanation".
        **EXAMPLE OF A GOOD RESPONSE:**
        { "question": "What is the formula for methane?", "options": { "A": "CH4", "B": "H2O", "C": "CO2", "D": "NaCl" }, "correct_answer": "A", "explanation": "Methane is a simple alkane with one carbon and four hydrogen atoms." }
        **EXAMPLE OF HOW TO REFUSE (IF CONTEXT IS THEORETICAL/INSUFFICIENT):**
        { "question": "Error: Theoretical Concept", "options": { "A": "", "B": "", "C": "", "D": "" }, "correct_answer": "A", "explanation": "The provided text is a theoretical concept and does not contain enough specific information to generate a practice question." }
        """
        response_params["response_format"] = {"type": "json_object"}
        response_params["temperature"] = 0.8
    else: # Default to 'explain' mode
        system_message = """You are an expert JEE tutor... **Crucially, you MUST enclose ALL mathematical formulas...**"""

    try:
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response_params["messages"] = messages
        response = llm_client.chat.completions.create(**response_params)
        content = response.choices[0].message.content.strip()

        if not content or content.lower().startswith("i'm sorry") or content.lower().startswith("i cannot"):
             raise HTTPException(status_code=503, detail="The AI was unable to generate a response.")

        if mode == 'practice':
            parsed_quiz = parse_quiz_json_from_string(content)
            if parsed_quiz is None:
                raise HTTPException(status_code=502, detail="The AI returned an invalid format for the quiz question. Please try again.")
            parsed_quiz['source_name'], parsed_quiz['source_level'] = context_name, context_level
            return JSONResponse(content=parsed_quiz)
        else:
            return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred while generating content.")