# backend/main.py

import os
import psycopg2 # Library for connecting to PostgreSQL
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from together import Together
from together.error import AuthenticationError

# --- Explicitly load the .env file from the backend directory ---
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

# --- Initialize Together AI Client ---
client = Together(api_key=TOGETHER_API_KEY)

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Connection Function ---
def get_db_connection():
    """Establishes and returns a connection to the Supabase database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"CRITICAL: Could not connect to the database. Error: {e}")
        return None


# === ENDPOINT 1: The "Dumb Test" - Generic Problem Generation ===
@app.post("/generate-llm-problem")
async def generate_llm_problem(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt")

    if not user_prompt:
        raise HTTPException(status_code=400, detail="User prompt is required for problem generation.")

    try:
        system_message = (
            "You are an expert-level AI physics and mathematics tutor. Your primary audience is students preparing for the IIT-JEE (Mains and Advanced) competitive exams in India. "
            "Your task is to generate a single, challenging, and non-trivial practice problem based on the user's request. "
            "The problem must be of 'JEE Advanced' difficulty, often requiring the synthesis of multiple concepts. "
            "Do NOT generate simple, textbook-style, or single-concept questions. Assume the user is highly intelligent and is looking for a challenge. "
            "Output ONLY the problem statement. Do not provide any hints, solutions, or explanations."
        )
        user_message_content = user_prompt

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message_content}
        ]

        response = client.chat.completions.create(
            model="meta-llama/Llama-3-8b-chat-hf",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        generated_text = response.choices[0].message.content.strip()

        return JSONResponse(
            status_code=200,
            content={"generated_text": generated_text}
        )
    except AuthenticationError as e:
        print(f"CRITICAL: Authentication Error with Together AI. Check your API Key. Details: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed with the AI service. Please check the backend API key.")
    except Exception as e:
        print(f"Error in LLM problem generation endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate problem via LLM. Backend error: {e}")


# === ENDPOINT 2: The "Smart Test" - RAG Explanation ===
@app.post("/explain-topic")
async def explain_topic(request: Request):
    """
    This is our new RAG endpoint. It fetches context from the database
    before calling the AI model.
    """
    data = await request.json()
    chapter_name = data.get("chapter_name")

    if not chapter_name:
        raise HTTPException(status_code=400, detail="Chapter name is required.")

    # --- 1. RETRIEVAL ---
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection is currently unavailable.")
    
    chapter_text = ""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT full_text FROM chapters WHERE name = %s LIMIT 1",
                (chapter_name,)
            )
            result = cur.fetchone()
            if result:
                chapter_text = result[0]
            else:
                raise HTTPException(status_code=404, detail=f"Chapter '{chapter_name}' not found in the knowledge base.")
    except psycopg2.Error as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while querying the database.")
    finally:
        conn.close()

    # --- 2. AUGMENTATION & 3. GENERATION ---
    try:
        system_message = (
            "You are an expert JEE tutor. Your task is to explain the key concepts from the provided textbook chapter. "
            "You are strictly forbidden from using any information you already know or any external knowledge. "
            "You MUST base your answer ONLY on the textbook chapter provided below. "
            "Structure your answer with clear headings and bullet points for readability."
        )
        
        user_message_content = (
            f"Using ONLY the provided textbook chapter, please explain the key concepts of '{chapter_name}'.\n\n"
            f"--- TEXTBOOK CHAPTER START ---\n"
            f"{chapter_text}\n"
            f"--- TEXTBOOK CHAPTER END ---"
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message_content}
        ]

        response = client.chat.completions.create(
            model="meta-llama/Llama-3-8b-chat-hf",
            messages=messages,
            max_tokens=1024,
            temperature=0.5,
        )
        generated_explanation = response.choices[0].message.content.strip()

        return JSONResponse(
            status_code=200,
            content={"explanation": generated_explanation}
        )
    except AuthenticationError as e:
        print(f"CRITICAL: Authentication Error with Together AI. Check your API Key. Details: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed with the AI service.")
    except Exception as e:
        print(f"Error in RAG explanation endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate explanation. Backend error: {e}")
