# backend/main.py

import os
import psycopg2
import json
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
origins = ["http://localhost", "http://localhost:5173"]
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

# === ENDPOINT 1: Fetch the entire syllabus structure ===
@app.get("/api/syllabus")
async def get_syllabus():
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    try:
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
        conn.close()

# === ENDPOINT 2: The Multi-Purpose Content Generator with Cascade Fallback ===
@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    topic_prompt = request.topic
    mode = request.mode

    topic_embedding = embedding_model.encode(topic_prompt).tolist()
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    relevant_text = ""
    context_level = ""
    context_name = ""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            if not match_result:
                raise HTTPException(status_code=404, detail=f"Could not find a relevant topic for '{topic_prompt}'.")
            
            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = match_result
            print(f"DEBUG: Found topic '{matched_topic_name}' (Similarity: {similarity:.4f})")

            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()

            if topic_text_result and topic_text_result[0] and topic_text_result[0].strip():
                print("DEBUG: Using TOPIC level context.")
                relevant_text = topic_text_result[0]
                context_level = "Topic"
                context_name = matched_topic_name
            else:
                print(f"DEBUG: Topic text empty. Falling back to CHAPTER level context (ID: {matched_chapter_id}).")
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                if chapter_text_result and chapter_text_result[1] and chapter_text_result[1].strip():
                    relevant_text = chapter_text_result[1]
                    context_level = "Chapter"
                    context_name = chapter_text_result[0]
                else:
                    raise HTTPException(status_code=404, detail=f"Sorry, content for '{matched_topic_name}' and its parent chapter is unavailable.")
    finally:
        conn.close()

    max_chars = 15000
    if len(relevant_text) > max_chars:
        relevant_text = relevant_text[:max_chars]

    user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
    response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4}

    if mode == 'revise':
        system_message = """
        You are an AI assistant creating a structured 'cheat sheet' for a student preparing for the JEE exam. Based ONLY on the provided context, generate a well-formatted summary.
        Your response MUST use Markdown formatting:
        - Use headings (like ## Key Definitions or ## Important Formulas) to separate sections.
        - Use bullet points (*) for lists.
        - Bold key terms using **asterisks**.
        - Use LaTeX for ALL mathematical formulas and variables, enclosing them in '$' or '$$'.
        """
    elif mode == 'practice':
        system_message = "You are an AI quiz generator. Based ONLY on the provided context, create one challenging, JEE-level multiple-choice question (MCQ). Your entire response must be a single, valid JSON object with keys: `question`, `options` (an object with A, B, C, D), `correct_answer`, and `explanation`. The value for `correct_answer` MUST BE one of the keys from the `options` object (e.g., 'A', 'B', 'C', or 'D'). Do not provide the text of the answer."
        response_params["response_format"] = {"type": "json_object"}
        response_params["temperature"] = 0.8
    else: # Default to 'explain' mode
        # --- THIS IS THE UPDATED, MORE EXPLICIT PROMPT ---
        system_message = "You are an expert JEE tutor. Your answer should be a clear, concise explanation of the topic based on the provided context. **Crucially, you MUST enclose ALL mathematical formulas, variables, and expressions in LaTeX delimiters.** Use single dollar signs (`$...$`) for inline math (like `$E=mc^2$`) and double dollar signs (`$$...$$`) for block equations. For example, write `$Φ_g = E⋅A$` instead of just Φg = E⋅A."

    try:
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response_params["messages"] = messages
        response = llm_client.chat.completions.create(**response_params)
        content = response.choices[0].message.content.strip()

        if mode == 'practice':
            final_response = json.loads(content)
            final_response['source_name'] = context_name
            final_response['source_level'] = context_level
            return JSONResponse(content=final_response)
        else:
            return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content. Backend error: {e}")