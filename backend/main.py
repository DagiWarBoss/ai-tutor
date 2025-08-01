# backend/main.py

import os
import psycopg2
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from together import Together
from together.error import AuthenticationError
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

# === ENDPOINT 1: The "Smart" RAG Pipeline for Questions ===
@app.post("/ask-question")
async def ask_question(request: Request):
    data = await request.json()
    user_question = data.get("question")

    if not user_question:
        raise HTTPException(status_code=400, detail="A question is required.")

    question_embedding = embedding_model.encode(user_question).tolist()

    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    relevant_chapter_text, found_chapter_name = "", ""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_chapters(%s::vector, 0.3, 1)", (question_embedding,))
            match_result = cur.fetchone()
            if not match_result:
                raise HTTPException(status_code=404, detail="Could not find a relevant chapter for your question.")

            matched_chapter_id, matched_chapter_name, similarity = match_result
            print(f"DEBUG: Found most similar chapter: '{matched_chapter_name}' (Similarity: {similarity:.4f})")
            
            cur.execute("SELECT full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
            text_result = cur.fetchone()
            if text_result:
                relevant_chapter_text, found_chapter_name = text_result[0], matched_chapter_name
    finally:
        conn.close()

    max_chars = 15000
    if len(relevant_chapter_text) > max_chars:
        relevant_chapter_text = relevant_chapter_text[:max_chars]

    try:
        system_message = "You are an expert JEE tutor..." # Abridged for brevity
        user_message_content = f"User's Question: '{user_question}'\n\n--- TEXTBOOK CHAPTER: {found_chapter_name} ---\n{relevant_chapter_text}\n--- END OF CHAPTER ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(model="mistralai/Mixtral-8x7B-Instruct-v0.1", messages=messages, max_tokens=1024, temperature=0.3)
        generated_answer = response.choices[0].message.content.strip()
        return JSONResponse(content={"answer": generated_answer, "source_chapter": found_chapter_name})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer. Backend error: {e}")

# === ENDPOINT 2: The "Smart" Problem Generator ===
@app.post("/generate-grounded-problem")
async def generate_grounded_problem(request: Request):
    data = await request.json()
    topic_prompt = data.get("topic")

    if not topic_prompt:
        raise HTTPException(status_code=400, detail="A topic is required.")

    topic_embedding = embedding_model.encode(topic_prompt).tolist()
    
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    relevant_chapter_text, found_chapter_name = "", ""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_chapters(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            if not match_result:
                raise HTTPException(status_code=404, detail=f"Could not find a relevant chapter for the topic '{topic_prompt}'.")

            matched_chapter_id, matched_chapter_name, similarity = match_result
            print(f"DEBUG: Found chapter '{matched_chapter_name}' (Similarity: {similarity:.4f}) to generate problem.")
            
            cur.execute("SELECT full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
            text_result = cur.fetchone()
            if text_result:
                relevant_chapter_text, found_chapter_name = text_result[0], matched_chapter_name
    finally:
        conn.close()

    max_chars = 15000
    if len(relevant_chapter_text) > max_chars:
        relevant_chapter_text = relevant_chapter_text[:max_chars]

    try:
        system_message = (
            "You are an expert-level AI physics and mathematics tutor... Format your entire response as a single, valid JSON object with exactly two keys: 'problem' and 'solution'."
        )
        
        user_message_content = f"User's Topic: '{topic_prompt}'\n\n--- TEXTBOOK CHAPTER: {found_chapter_name} ---\n{relevant_chapter_text}\n--- END OF CHAPTER ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages,
            max_tokens=2048,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        
        response_content = response.choices[0].message.content.strip()
        parsed_json = json.loads(response_content)
        problem = parsed_json.get("problem", "Error: Could not generate problem.")
        solution = parsed_json.get("solution", "Error: Could not generate solution.")

        return JSONResponse(content={"problem": problem, "solution": solution, "source_chapter": found_chapter_name})
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="The AI model returned an invalid format. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate problem. Backend error: {e}")

# === ENDPOINT 3: Fetch the entire syllabus structure (OPTIMIZED) ===
@app.get("/api/syllabus")
async def get_syllabus():
    """
    Fetches the entire structured syllabus from the database using an efficient,
    low-query method to prevent slow load times.
    """
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    try:
        with conn.cursor() as cur:
            # Step 1: Fetch all data in as few queries as possible
            cur.execute("SELECT id, name, class_level FROM subjects ORDER BY class_level, name")
            subjects_raw = cur.fetchall()
            
            cur.execute("SELECT id, name, chapter_number, subject_id FROM chapters ORDER BY chapter_number")
            chapters_raw = cur.fetchall()
            
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY id")
            topics_raw = cur.fetchall()

            # Step 2: Process the data in Python using maps for efficiency
            subjects_map = {
                s_id: {"id": s_id, "name": s_name, "class_level": s_class, "chapters": []}
                for s_id, s_name, s_class in subjects_raw
            }
            
            chapters_map = {
                c_id: {"id": c_id, "name": c_name, "number": c_num, "topics": []}
                for c_id, c_name, c_num, s_id in chapters_raw
            }

            # Step 3: Link topics to chapters
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map:
                    chapters_map[c_id]["topics"].append({
                        "id": t_id,
                        "name": t_name,
                        "number": t_num
                    })

            # Step 4: Link chapters to subjects
            for c_id, c_name, c_num, s_id in chapters_raw:
                if s_id in subjects_map:
                    subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            
            # Final structure is the list of values from the subjects map
            syllabus = list(subjects_map.values())

        return JSONResponse(content=syllabus)
        
    except psycopg2.Error as e:
        print(f"Database query error while fetching syllabus: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        conn.close()
