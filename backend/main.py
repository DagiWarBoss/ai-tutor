# backend/main.py

import os
import psycopg2
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
# This loads the AI model for generating text
llm_client = Together(api_key=TOGETHER_API_KEY)
# This loads the AI model for creating embeddings (the "smart librarian")
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

# === ENDPOINT: The Final, "Smartest" RAG Pipeline ===
@app.post("/ask-question")
async def ask_question(request: Request):
    data = await request.json()
    user_question = data.get("question")

    if not user_question:
        raise HTTPException(status_code=400, detail="A question is required.")

    # --- 1. Create an embedding for the user's question ---
    print(f"DEBUG: Creating embedding for question: '{user_question}'")
    question_embedding = embedding_model.encode(user_question).tolist()

    # --- 2. RETRIEVAL (Semantic Search) ---
    # Use our new database function to find the most relevant chapter.
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable.")
    
    relevant_chapter_text = ""
    found_chapter_name = ""
    try:
        with conn.cursor() as cur:
            # Call the match_chapters function in the database
            cur.execute(
                "SELECT * FROM match_chapters(%s, 0.5, 1)",
                (question_embedding,)
            )
            match_result = cur.fetchone()

            if not match_result:
                raise HTTPException(status_code=404, detail="Could not find a relevant chapter for your question.")

            matched_chapter_id, matched_chapter_name, similarity = match_result
            print(f"DEBUG: Found most similar chapter: '{matched_chapter_name}' (Similarity: {similarity:.4f})")
            
            # Now, fetch the full text of that chapter
            cur.execute("SELECT full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
            text_result = cur.fetchone()
            if text_result:
                relevant_chapter_text = text_result[0]
                found_chapter_name = matched_chapter_name
    except psycopg2.Error as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Error querying the database.")
    finally:
        conn.close()

    # Truncate the text to avoid exceeding the model's context limit
    max_chars = 15000
    if len(relevant_chapter_text) > max_chars:
        relevant_chapter_text = relevant_chapter_text[:max_chars]

    # --- 3. AUGMENTATION & 4. GENERATION ---
    try:
        system_message = (
            "You are an expert JEE tutor. Your task is to answer the user's question based on the provided textbook chapter. "
            "You are strictly forbidden from using any external knowledge. "
            "You MUST base your answer ONLY on the provided text. If the answer is not in the text, say 'The answer to that question is not found in the provided chapter text.'"
        )
        
        user_message_content = (
            f"User's Question: '{user_question}'\n\n"
            f"--- TEXTBOOK CHAPTER: {found_chapter_name} ---\n"
            f"{relevant_chapter_text}\n"
            f"--- END OF CHAPTER ---"
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message_content}
        ]

        response = llm_client.chat.completions.create(
            model="meta-llama/Llama-3-8b-chat-hf",
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        generated_answer = response.choices[0].message.content.strip()

        return JSONResponse(
            status_code=200,
            content={
                "answer": generated_answer,
                "source_chapter": found_chapter_name
            }
        )
    except Exception as e:
        print(f"Error in RAG answer generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate answer. Backend error: {e}")
