import os
import sys
import traceback
import psycopg2
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from together import Together
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# --- DEBUG: Print environment variables ---
print("---- ENVIRONMENT VARIABLES ----")
for key, value in os.environ.items():
    if "DB" in key or "API" in key or "SUPABASE" in value:
        print(f"{key}={value}")

# Load .env
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
print(f"Attempting to load .env from {dotenv_path}")
load_dotenv(dotenv_path=dotenv_path)
print(".env loaded")

# API & DB config
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

print("DB config loaded:", DB_HOST, DB_USER, DB_NAME, DB_PORT)

# Initialize AI client (LLM client initialization does not block)
llm_client = Together(api_key=TOGETHER_API_KEY)

# Lazy loading for embedding model
embedding_model = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        try:
            embedding_model = SentenceTransformer('all-MiniLM-L6')
            print("Embedding model loaded successfully on first use.")
        except Exception as e:
            print(f"Error loading model: {e}")
            traceback.print_exc()
            raise e
    return embedding_model

class ContentRequest(BaseModel):
    topic: str
    mode: str

class GoogleLoginRequest(BaseModel):
    token: str

class FeatureRequest(BaseModel):
    user_email: str
    feature_text: str

app = FastAPI()

origins = [
    "https://praxisai-rho.vercel.app",
    "https://praxis-ai.fly.dev",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root route to handle "/" and avoid 404
@app.get("/")
async def root():
    return {"message": "Welcome to the Praxis AI backend API"}

# Health check endpoint to support Fly.io health checks
@app.get("/health")
async def health():
    return {"status": "ok"}

def get_db_connection():
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
        print(f"Database connection error: {e}")
        traceback.print_exc()
        return None

def parse_quiz_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^``````$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            q = re.search(r'"question":\s*"([^"]+)"', text, re.DOTALL)
            opts = re.findall(r'"([A-D])":\s*"([^"]+)"', text, re.DOTALL)
            ans = re.search(r'"correct_answer":\s*"([^"]+)"', text, re.DOTALL)
            expl = re.search(r'"explanation":\s*"([^"]+)"', text, re.DOTALL)
            if not (q and opts and ans and expl):
                return None
            options = {k: v for k, v in opts}
            if len(options) != 4:
                return None
            return {
                "question": q.group(1),
                "options": options,
                "correct_answer": ans.group(1),
                "explanation": expl.group(1),
            }
        except Exception:
            return None

THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

@app.get("/api/syllabus")
async def get_syllabus():
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        cur = conn.cursor()

        cur.execute("SELECT id, name FROM subjects ORDER BY name")
        subjects = cur.fetchall()  # (id, name)

        cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number, chapter_number")
        chapters = cur.fetchall()  # (id, name, chapter_number, subject_id, class_number)

        cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
        topics = cur.fetchall()  # (id, name, topic_number, chapter_id)

        chapters_map = {}
        for c in chapters:
            chapters_map[c[0]] = {
                "name": c[1],
                "chapter_number": c[2],      # Capture chapter_number from DB
                "subject_id": c[3],
                "class_number": c,
                "topics": []
            }

        for t in topics:
            topic_name = t[1]
            topic_number = t[2]
            chapter_id = t[3]
            if chapter_id in chapters_map:
                chapters_map[chapter_id]["topics"].append({
                    "name": topic_name,
                    "topic_number": topic_number
                })

        subjects_map = {}
        for s in subjects:
            subject_id, subject_name = s
            subjects_map[subject_id] = {
                "name": subject_name,
                "chapters": []
            }

        for c in chapters:
            chapter_id = c[0]
            subject_id = c[3]
            if subject_id in subjects_map and chapter_id in chapters_map:
                subjects_map[subject_id]["chapters"].append(chapters_map[chapter_id])

        syllabus = list(subjects_map.values())
        return JSONResponse(content=syllabus)

    except Exception as e:
        print(f"Error loading syllabus: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error loading syllabus")
    finally:
        conn.close()

@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    conn = None
    try:
        model = get_embedding_model()
        embedding = model.encode(request.topic).tolist()
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        cur = conn.cursor()
        cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (embedding,))
        result = cur.fetchone()
        if not result:
            return JSONResponse({"error": "No matching topic found", "question": None})
        topic_id, topic_name, similarity, chapter_id = result
        if topic_name.strip().lower() in THEORETICAL_TOPICS:
            return JSONResponse({"error": "Practice not applicable", "question": None})
        cur.execute("SELECT full_text FROM topics WHERE id = %s", (topic_id,))
        data = cur.fetchone()
        text = data[0] if data and data.strip() else None
        if not text:
            cur.execute("SELECT full_text FROM chapters WHERE id = %s", (chapter_id,))
            data = cur.fetchone()
            text = data if data and data.strip() else ""
        user_msg = f"User wants to learn about '{request.topic}'. Context:\n{text}"
        params = {
            "model": "mistralai/Mixtral-8b-Instruct",
            "max_tokens": 2048,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": "Generate quiz question."},
                {"role": "user", "content": user_msg}
            ]
        }
        resp = llm_client.chat.completions.create(**params)
        content = resp.choices[0].message.content.strip()
        quiz = parse_quiz_json(content)
        if quiz is None:
            raise HTTPException(status_code=502, detail="Invalid quiz format")
        return JSONResponse(quiz)
    except Exception as e:
        print(f"Error generating content: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="AI content generation failed")
    finally:
        if conn:
            conn.close()

@app.post("/api/google-login")
async def google_login(data: GoogleLoginRequest):
    conn = None
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            "621306164868-21bamnrurup0nk6f836fss6q92s04aav.apps.googleusercontent.com"
        )
        email = idinfo.get("email")
        name = idinfo.get("name")
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (email, name)
            VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
            """, (email, name))
        conn.commit()
        return {"email": email, "name": name}
    except Exception as e:
        print(f"Google login failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid login")
    finally:
        if conn:
            conn.close()

@app.post("/api/feature-request")
async def submit_feature(request: FeatureRequest):
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO feature_requests (user_email, feature_text) VALUES (%s,%s)",
                    (request.user_email, request.feature_text))
        conn.commit()
        return {"message": "Feature request submitted"}
    except Exception as e:
        print(f"Feature request save failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save feature request")
    finally:
        conn.close()
