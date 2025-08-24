import os
import sys
import traceback
import psycopg2
import json
import re
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from together import Together
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# --- Debug Environment Variables ---
for key, value in os.environ.items():
    if "DB" in key or "API" in key or "SUPABASE" in value:
        print(f"{key}={value}")

# Load environment variables from .env file
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
print(f"Loading .env from {dotenv_path}")
load_dotenv(dotenv_path)
print(".env loaded")

# Configurations
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

print(f"DB configurations: Host={DB_HOST}, User={DB_USER}, DB={DB_NAME}, Port={DB_PORT}")

# Initialize AI clients
llm_client = Together(api_key=TOGETHER_API_KEY)
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded successfully.")
except Exception as e:
    print("Error loading embedding model:", e)
    traceback.print_exc()
    sys.exit(1)

# Pydantic request models
class ContentRequest(BaseModel):
    topic: str
    mode: str

class GoogleLoginRequest(BaseModel):
    token: str

class FeatureRequest(BaseModel):
    user_email: str
    feature_text: str

# Initialize FastAPI app
app = FastAPI()

# CORS configuration
origins = [
    "https://praxisai-rho.app",
    "https://praxis-ai.fly.dev",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check Endpoint - For Fly.io and others
@app.get("/health")
async def health():
    return {"status": "ok"}

# OPTIONS method handler to handle preflight CORS requests
@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path):
    return Response(status_code=200)

# Helper function for DB connection
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        print("Database connection established")
        return conn
    except Exception as e:
        print("Database connection error:", e)
        traceback.print_exc()
        return None

# Parse quiz JSON safely with fallback parsing
def parse_quiz_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^``````$", "", text).strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            question_match = re.search(r'"question":\s*"(.*?)"', text, re.DOTALL)
            options_match = re.search(r'"options":\s*\{(.*?)\}', text, re.DOTALL)
            answer_match = re.search(r'"correct_answer":\s*"(.*?)"', text, re.DOTALL)
            explanation_match = re.search(r'"explanation":\s*"(.*?)"', text, re.DOTALL)
            if not all([question_match, options_match, answer_match, explanation_match]):
                return None

            question = question_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            options_raw = options_match.group(1)
            options = dict(re.findall(r'"([A-D])":\s*"(.*?)"', options_raw))
            if len(options) != 4:
                return None

            correct_answer = answer_match.group(1)
            explanation = explanation_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            
            return {
                "question": question.strip(),
                "options": options,
                "correct_answer": correct_answer.strip(),
                "explanation": explanation.strip(),
            }
        except Exception as e:
            print("Error parsing quiz JSON fallback:", e)
            traceback.print_exc()
            return None

# Predefined topics to exclude quizzes on
THEORETICAL_TOPICS = {"introduction", "overview", "basics", "fundamentals"}

# Syllabus endpoint
@app.get("/api/syllabus")
async def syllabus():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database unavailable")

        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM subjects ORDER BY name")
            subjects = cur.fetchall()

            cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number")
            chapters = cur.fetchall()

            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
            topics = cur.fetchall()

            chapter_map = {}
            for c_id, c_name, c_num, s_id, c_level in chapters:
                chapter_map[c_id] = {
                    "id": c_id,
                    "name": c_name,
                    "number": c_num,
                    "class_level": c_level,
                    "topics": []
                }

            for t_id, t_name, t_num, c_id in topics:
                if c_id in chapter_map:
                    chapter_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})

            subject_map = {s_id: {"id": s_id, "name": s_name, "chapters": []} for s_id, s_name in subjects}

            for c in chapters:
                s_id = c[3]
                if s_id in subject_map:
                    subject_map[s_id]["chapters"].append(chapter_map[c[0]])

            syllabus_data = list(subject_map.values())
            return JSONResponse(content=syllabus_data)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch syllabus")
    finally:
        if conn:
            conn.close()

# Generate content endpoint
@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    conn = None
    try:
        topic = request.topic
        mode = request.mode
        embedding_vec = embedding_model.encode(topic).tolist()

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database unavailable")

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (embedding_vec,))
            matched = cur.fetchone()

            if not matched:
                return {"question": None, "error": "No suitable topic found.", "source_name": topic, "source_level": "Query"}

            topic_id, topic_name, sim_score, chapter_id = matched
            if topic_name.lower() in THEORETICAL_TOPICS:
                return {"question": None, "error": "No suitable quiz available for theoretical topics.", "source_name": topic_name, "source_level": "Topic"}

            cur.execute("SELECT full_text FROM topics WHERE id=%s", (topic_id,))
            topic_text_res = cur.fetchone()

            if topic_text_res and topic_text_res[0].strip():
                content_text = topic_text_res[0]
                content_context = "Topic"
                content_name = topic_name
            else:
                cur.execute("SELECT name, full_text FROM chapters WHERE id=%s", (chapter_id,))
                chapter_text_res = cur.fetchone()
                if chapter_text_res and chapter_text_res[1].strip():
                    content_text = chapter_text_res[1]
                    content_context = "Chapter"
                    content_name = chapter_text_res[0]
                else:
                    return {"question": None, "error": "No suitable content found for quiz.", "source_name": topic_name, "source_level": "Topic"}

            if mode == "practice" and content_context == "Chapter" and content_name.lower() in THEORETICAL_TOPICS:
                return {"question": None, "error": "Quizzes not supported for basic topics.", "source_name": content_name, "source_level": content_context}

            # Limit context length
            max_length = 15000
            if len(content_text) > max_length:
                content_text = content_text[:max_length]

            unique_id = f"req-{int(time.time())}-{os.urandom(4).hex()}"
            prompt = (
                f"User wants to learn about '{topic}'.\n\n"
                f"Context ({content_context}: {content_name}):\n{content_text}\n"
                f"Generate a unique question for this request ID: {unique_id}"
            )

            system_message = ""
            if mode == "revise":
                system_message = "You are an assistant creating structured notes."
            elif mode == "practice":
                system_message = (
                    "You are an expert quiz generator for JEE students. "
                    "Respond only with valid JSON per template: question, options {A-D}, correct_answer, explanation."
                )
            else:
                system_message = "You are an AI teacher."

            params = {
                "model": "mistralai/Mixtral-8B",
                "max_tokens": 2048,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
            }

            response = llm_client.chat.completions.create(**params)
            text_response = response.choices[0].message.content.strip()

            if not text_response or text_response.lower().startswith(("i'm sorry", "i cannot")):
                raise HTTPException(status_code=503, detail="AI did not generate a valid response")

            if mode == "practice":
                quiz = parse_quiz_json(text_response)
                if quiz is None:
                    # Fallback to chapter context
                    cur.execute("SELECT full_text, name FROM chapters WHERE id=%s", (chapter_id,))
                    chapter_res = cur.fetchone()
                    if chapter_res:
                        fallback_prompt = (
                            f"User wants to learn about '{topic}'.\n"
                            f"Context (Chapter: {chapter_res[1]}):\n{chapter_res[0]}"
                        )
                        params["messages"][1]["content"] = fallback_prompt
                        response = llm_client.chat.completions.create(**params)
                        fallback_text = response.choices[0].message.content.strip()
                        quiz = parse_quiz_json(fallback_text)
                        if quiz is not None:
                            quiz["source_name"] = chapter_res[1]
                            quiz["source_level"] = "Chapter"
                            return quiz
                    raise HTTPException(status_code=502, detail="AI did not return valid quiz JSON")
                quiz["source_name"] = content_name
                quiz["source_level"] = content_context
                return quiz

            return {"content": text_response, "source_name": content_name, "source_level": content_context}

    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(ex))
    finally:
        if conn:
            conn.close()

# Google Login Endpoint
@app.post("/api/google-login")
async def google_login(data: GoogleLoginRequest):
    try:
        id_data = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            "621306164868.apps.googleusercontent.com"  # Replace with your Client ID
        )
        email = id_data.get("email")
        name = id_data.get("name")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database unavailable")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users(email, name) VALUES (%s, %s) ON CONFLICT(email) DO UPDATE SET name=EXCLUDED.name
                """,
                (email, name),
            )
            conn.commit()
        return {"email": email, "name": name}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid token or DB error")
    finally:
        if conn:
            conn.close()

# Feature Request Endpoint
@app.post("/api/feature-request")
async def feature_request(req: FeatureRequest):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feature_requests(user_email, feature_text) VALUES (%s, %s)",
                (req.user_email, req.feature_text),
            )
            conn.commit()
        return {"message": "Feature request submitted successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to submit feature request")
    finally:
        if conn:
            conn.close()
