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
            cur.execute("SELECT id, name, class_level FROM subjects ORDER BY class_level, name")
            subjects_raw = cur.fetchall()
            cur.execute("SELECT id, name, chapter_number, subject_id FROM chapters ORDER BY subject_id, chapter_number")
            chapters_raw = cur.fetchall()
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, id")
            topics_raw = cur.fetchall()

            chapters_map = {c_id: {"id": c_id, "name": c_name, "number": c_num, "topics": []} for c_id, c_name, c_num, s_id in chapters_raw}
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map:
                    chapters_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})
            subjects_map = {s_id: {"id": s_id, "name": s_name, "class_level": s_class, "chapters": []} for s_id, s_name, s_class in subjects_raw}
            for c_id, c_name, c_num, s_id in chapters_raw:
                if s_id in subjects_map:
                    subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            syllabus = list(subjects_map.values())
        return JSONResponse(content=syllabus)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        conn.close()

# === ENDPOINT 2: The Multi-Purpose Content Generator ===
@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    topic_prompt = request.topic
    mode = request.mode

    topic_embedding = embedding_model.encode(topic_prompt).tolist()
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    relevant_topic_text = ""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            if not match_result:
                raise HTTPException(status_code=404, detail=f"Could not find a relevant topic for '{topic_prompt}'.")
            matched_topic_id, matched_topic_name, similarity = match_result
            print(f"DEBUG: Found topic '{matched_topic_name}' (Similarity: {similarity:.4f}) for mode '{mode}'.")
            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            text_result = cur.fetchone()
            if text_result:
                relevant_topic_text = text_result[0]
    finally:
        conn.close()

    max_chars = 15000
    if len(relevant_topic_text) > max_chars:
        relevant_topic_text = relevant_topic_text[:max_chars]

    system_message = ""
    user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ---\n{relevant_topic_text}\n--- END OF CONTEXT ---"
    response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4}

    if mode == 'revise':
        # --- THIS IS THE UPDATED PROMPT ---
        system_message = """
        You are an AI assistant creating a structured 'cheat sheet' for a student preparing for the JEE exam. Based ONLY on the provided context, generate a well-formatted summary.

        Your response MUST use Markdown formatting:
        - Use headings (like ## Key Definitions or ## Important Formulas) to separate sections.
        - Use bullet points (*) for lists.
        - Bold key terms using **asterisks**.
        - Use LaTeX for ALL mathematical formulas and variables, enclosing them in '$' or '$$'.
        """
    elif mode == 'practice':
        system_message = "You are an AI quiz generator. Based ONLY on the provided context, create one challenging, JEE-level multiple-choice question (MCQ). Your entire response must be a single, valid JSON object with keys: `question`, `options` (an object with A, B, C, D), `correct_answer` ('A', 'B', 'C', or 'D'), and `explanation`."
        response_params["response_format"] = {"type": "json_object"}
        response_params["temperature"] = 0.8
    else: # Default to 'explain' mode
        system_message = "You are an expert JEE tutor. Your answer should be a clear, concise explanation of the topic based on the provided context. Use LaTeX for all mathematical formulas, enclosing inline math with '$' and block equations with '$$'."

    try:
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response_params["messages"] = messages
        
        response = llm_client.chat.completions.create(**response_params)
        content = response.choices[0].message.content.strip()

        if mode == 'practice':
            return JSONResponse(content=json.loads(content))
        else:
            return JSONResponse(content={"content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content. Backend error: {e}")