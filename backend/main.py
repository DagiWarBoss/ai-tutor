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

# Load .env
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# API & DB config
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

llm_client = Together(api_key=TOGETHER_API_KEY)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

class ContentRequest(BaseModel):
    topic: str
    mode: str

app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"CRITICAL: Could not connect to the database. Error: {e}")
        return None

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
                print("DEBUG: Regex parsing failed to find all required fields.")
                return None

            question = question_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')
            options_str = options_match.group(1)
            correct_answer = answer_match.group(1).strip()
            explanation = explanation_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')

            options = {}
            option_matches = re.findall(r'"([A-D])":\s*"(.*?)"', options_str)
            for key, value in option_matches:
                options[key] = value.strip().replace('\\n', '\n').replace('\\"', '"')

            if len(options) != 4:
                print("DEBUG: Regex failed to parse all 4 options.")
                return None

            return {
                "question": question,
                "options": options,
                "correct_answer": correct_answer,
                "explanation": explanation
            }
        except Exception as e:
            print(f"DEBUG: Regex parsing encountered an unexpected error: {e}")
            return None

THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

@app.get("/api/syllabus")
async def get_syllabus():
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM subjects ORDER BY name")
            subjects_raw = cur.fetchall()
            cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number, chapter_number")
            chapters_raw = cur.fetchall()
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
            topics_raw = cur.fetchall()
            chapters_map = {
                c_id: {"id": c_id, "name": c_name, "number": c_num, "class_level": c_level, "topics": []}
                for c_id, c_name, c_num, s_id, c_level in chapters_raw
            }
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map:
                    chapters_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})
            subjects_map = {s_id: {"id": s_id, "name": s_name, "chapters": []} for s_id, s_name in subjects_raw}
            for c_id, c_name, c_num, s_id, c_level in chapters_raw:
                if s_id in subjects_map:
                    subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            syllabus = list(subjects_map.values())
        return JSONResponse(content=syllabus)
    except psycopg2.Error as e:
        print(f"Database query error while fetching syllabus: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        if conn:
            conn.close()

@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    topic_prompt = request.topic
    mode = request.mode
    conn = None

    try:
        topic_embedding = embedding_model.encode(topic_prompt).tolist()
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        
        relevant_text = ""
        context_level = ""
        context_name = ""
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            if not match_result:
                raise HTTPException(status_code=404, detail=f"Could not find a relevant topic for '{topic_prompt}'.")
            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = match_result
            print(f"DEBUG: Found topic '{matched_topic_name}' (Similarity: {similarity:.4f})")

            # Explicitly handle theoretical topics
            if matched_topic_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={
                    "question": None,
                    "error": "This is a Theoretical Concept",
                    "source_name": matched_topic_name,
                    "source_level": "Topic"
                })

            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()
            # ---- FIXED: Call .strip() on the string, NOT the tuple
            if topic_text_result and topic_text_result[0] and topic_text_result.strip():
                relevant_text = topic_text_result
                context_level = "Topic"
                context_name = matched_topic_name
            else:
                print(f"DEBUG: Topic text empty. Falling back to CHAPTER level context (ID: {matched_chapter_id}).")
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                # ---- FIXED: Call .strip() on chapter_text_result[1], NOT chapter_text_result
                if chapter_text_result and chapter_text_result[1] and chapter_text_result[1].strip():
                    relevant_text = chapter_text_result[1]
                    context_level = "Chapter"
                    context_name = chapter_text_result
                else:
                    raise HTTPException(status_code=404, detail=f"Sorry, content for '{matched_topic_name}' and its parent chapter is unavailable.")

        if mode == "practice" and context_level == "Chapter":
            if context_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={
                    "question": None,
                    "error": "This is a Theoretical Concept",
                    "source_name": context_name,
                    "source_level": context_level
                })

        max_chars = 15000
        if len(relevant_text) > max_chars:
            relevant_text = relevant_text[:max_chars]

        user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
        response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4}
        system_message = ""

        if mode == 'revise':
            system_message = "..."  # your revise prompt
        elif mode == 'practice':
            system_message = """
            You are an expert AI quiz generator. Your task is to create one multiple-choice question (MCQ) based ONLY on the provided context.
            **CRITICAL INSTRUCTIONS:**
            1. Your entire response MUST be a single, valid JSON object.
            2. The JSON object must have EXACTLY these keys: "question", "options", "correct_answer", "explanation".
            3. The "options" value must be another JSON object with keys "A", "B", "C", and "D".
            4. The "correct_answer" value MUST be a single letter: "A", "B", "C", or "D".
            **EXAMPLE OUTPUT FORMAT:**
            { "question": "What is the capital of France?", "options": { "A": "London", "B": "Berlin", "C": "Paris", "D": "Madrid" }, "correct_answer": "C", "explanation": "Paris is the capital and most populous city of France." }
            """
            response_params["response_format"] = {"type": "json_object"}
            response_params["temperature"] = 0.8
        else:
            system_message = "..."

        try:
            messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
            response_params["messages"] = messages

            response = llm_client.chat.completions.create(**response_params)
            content = response.choices[0].message.content.strip()

            if not content or content.lower().startswith("i'm sorry") or content.lower().startswith("i cannot"):
                raise HTTPException(
                    status_code=503,
                    detail="The AI was unable to generate a response for this topic, possibly due to limited source text. Please try another topic."
                )

            if mode == 'practice':
                parsed_quiz = parse_quiz_json_from_string(content)

                if parsed_quiz is None:
                    raise HTTPException(
                        status_code=502,
                        detail="The AI returned an invalid format for the quiz question. Please try again."
                    )

                parsed_quiz['source_name'] = context_name
                parsed_quiz['source_level'] = context_level
                return JSONResponse(content=parsed_quiz)
            else:
                return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"An unexpected error occurred during AI call: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while generating content.")
    finally:
        if conn:
            conn.close()
