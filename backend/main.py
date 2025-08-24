import os
import sys
import traceback
import psycopg2
import json
import re
import random
import time
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from together import Together
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi.middleware.cors import CORSMiddleware

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

# Initialize AI and Embedding clients
llm_client = Together(api_key=TOGETHER_API_KEY)
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"Error loading embedding model: {e}")
    traceback.print_exc()
    sys.exit(1)

class ContentRequest(BaseModel):
    topic: str
    mode: str

class GoogleLoginRequest(BaseModel):
    token: str

class FeatureRequest(BaseModel):
    user_email: str
    feature_text: str

# --- FastAPI and CORS ---
app = FastAPI()
origins = [
    "https://praxisai-rho.vercel.app",
    "https://praxis-ai.fly.dev",
    "http://localhost:8080",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://praxisai-rho.vercel.app",
        "https://praxis-ai.fly.dev",
        # (add localhost for local dev too)
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    return Response(status_code=200)

def get_db_connection():
    try:
        print("Trying DB connection...")
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        print("DB connect success.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"CRITICAL: Could not connect to the database. Error: {e}")
        traceback.print_exc()
        return None

def parse_quiz_json_from_string(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^\\`\\`\\`json\\`\\`\\`|\\`\\`\\`$", "", text).strip()
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
            if len(options) != 4:
                return None
            return {"question": question, "options": options, "correct_answer": correct_answer, "explanation": explanation}
        except Exception as e:
            print(f"DEBUG: Regex parsing encountered an unexpected error: {e}")
            traceback.print_exc()
            return None

THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

@app.get("/api/syllabus")
async def get_syllabus():
    print("GET /api/syllabus called")
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            print("Running syllabus DB queries...")
            cur.execute("SELECT id, name FROM subjects ORDER BY name")
            subjects_raw = cur.fetchall()
            cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number, chapter_number")
            chapters_raw = cur.fetchall()
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
            topics_raw = cur.fetchall()
            chapters_map = {c_id: {"id": c_id, "name": c_name, "number": c_num, "class_level": c_level, "topics": []} for c_id, c_name, c_num, s_id, c_level in chapters_raw}
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map:
                    chapters_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})
            subjects_map = {s_id: {"id": s_id, "name": s_name, "chapters": []} for s_id, s_name in subjects_raw}
            for c_id, c_name, c_num, s_id, c_level in chapters_raw:
                if s_id in subjects_map:
                    subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            syllabus = list(subjects_map.values())
        print("Syllabus query success.")
        return JSONResponse(content=syllabus)
    except psycopg2.Error as e:
        print(f"Database query error while fetching syllabus: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        if conn:
            conn.close()

@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    print("POST /api/generate-content called with:", request)
    topic_prompt = request.topic
    mode = request.mode
    conn = None
    try:
        topic_embedding = embedding_model.encode(topic_prompt).tolist()
        print("Embedding generated successfully.")

        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")

        relevant_text, context_level, context_name = "", "", ""
        with conn.cursor() as cur:
            print("Finding matching topic in DB...")
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 1)", (topic_embedding,))
            match_result = cur.fetchone()
            print("Match result:", match_result)
            if not match_result:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": topic_prompt, "source_level": "User Query"})

            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = match_result
            print(f"DEBUG: Found topic '{matched_topic_name}' (Similarity: {similarity:.4f})")
            if matched_topic_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": matched_topic_name, "source_level": "Topic"})

            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()

            if topic_text_result and topic_text_result[0] and topic_text_result.strip():
                relevant_text, context_level, context_name = topic_text_result, "Topic", matched_topic_name
            else:
                print(f"DEBUG: Topic text empty. Falling back to CHAPTER level context (ID: {matched_chapter_id}).")
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                if chapter_text_result and chapter_text_result[1] and chapter_text_result[9].strip():
                    relevant_text, context_level, context_name = chapter_text_result[9], "Chapter", chapter_text_result
                else:
                    return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": matched_topic_name, "source_level": "Topic"})

        if mode == "practice" and context_level == "Chapter":
            if context_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": context_name, "source_level": context_level})

        max_chars = 15000
        if len(relevant_text) > max_chars:
            relevant_text = relevant_text[:max_chars]

        unique_id = f"UniqueRequestID_{int(time.time())}_{random.randint(1, 100000)}"
        user_message_content = (
            f"The user wants to learn about the topic: '{topic_prompt}'.\n\n"
            f"--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n"
            f"{relevant_text}\n"
            f"--- END OF CONTEXT ---\n"
            f"Please generate a new and unique practice question for this. Request ID: {unique_id}"
        )

        response_params = {
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "max_tokens": 2048,
            "temperature": 0.4,
        }
        system_message = ""

        if mode == 'revise':
            system_message = """You are an AI assistant creating a structured 'cheat sheet' for JEE topics."""
        elif mode == 'practice':
            system_message = (
                "You are an expert AI quiz generator for JEE students. "
                "Given textbook context, respond ONLY with a valid JSON object matching this template: "
                '{'
                '"question": "...", '
                '"options": { "A": "...", "B": "...", "C": "...", "D": "..." }, '
                '"correct_answer": "...", '
                '"explanation": "..." '
                '}. '
                "Do not include any explanations, comments, or Markdown. ONLY output strict JSON—no extra formatting."
            )
        else:
            system_message = """You are an expert JEE tutor."""

        try:
            print("Calling LLM API for response...")
            messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
            response_params["messages"] = messages
            response = llm_client.chat.completions.create(**response_params)
            content = response.choices[0].message.content.strip()
            print("LLM response received.")
            if not content or content.lower().startswith("i'm sorry") or content.lower().startswith("i cannot"):
                print("LLM refused to answer.")
                raise HTTPException(status_code=503, detail="The AI was unable to generate a response.")
            if mode == 'practice':
                parsed_quiz = parse_quiz_json_from_string(content)
                if parsed_quiz is None:
                    print("LLM returned invalid format for quiz. Try fallback on chapter context.")
                    with conn.cursor() as cur:
                        cur.execute("SELECT full_text, name FROM chapters WHERE id = %s", (matched_chapter_id,))
                        chapter_result = cur.fetchone()
                        if chapter_result and chapter_result[0] and chapter_result.strip():
                            chapter_text, chapter_name = chapter_result
                            fallback_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK (Chapter: {chapter_name}) ---\n{chapter_text}\n--- END OF CONTEXT ---"
                            fallback_messages = [{"role": "system", "content": system_message}, {"role": "user", "content": fallback_message_content}]
                            fallback_response = llm_client.chat.completions.create(
                                model=response_params["model"],
                                max_tokens=response_params["max_tokens"],
                                temperature=response_params["temperature"],
                                messages=fallback_messages
                            )
                            fallback_content = fallback_response.choices[0].message.content.strip()
                            parsed_fallback = parse_quiz_json_from_string(fallback_content)
                            if parsed_fallback:
                                parsed_fallback['source_name'], parsed_fallback['source_level'] = chapter_name, "Chapter"
                                print("Fallback quiz generated from chapter context.")
                                return JSONResponse(content=parsed_fallback)
                    print("AI returned invalid format for both topic and chapter context.")
                    raise HTTPException(status_code=502, detail="The AI returned an invalid format for both topic and chapter context.")
                parsed_quiz['source_name'], parsed_quiz['source_level'] = context_name, context_level
                print("Quiz generated and returned.")
                return JSONResponse(content=parsed_quiz)
            else:
                print("Learn/revise content returned.")
                return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
        except HTTPException as e:
            print("HTTP exception:", e)
            traceback.print_exc()
            raise e
        except Exception as e:
            print("An unexpected error occurred during AI call:", e)
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    finally:
        if conn:
            conn.close()
        print("DB connection closed (if any).")

@app.post("/api/google-login")
async def google_login(data: GoogleLoginRequest):
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            "621306164868-21bamnrurup0nk6f836fss6q92s04aav.apps.googleusercontent.com"  # Your Google OAuth Client ID
        )
        email = idinfo.get("email")
        name = idinfo.get("name")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, name)
                VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                """,
                (email, name)
            )
            conn.commit()
        print(f"Google login success for: {email}")
        return {"email": email, "name": name}
    except Exception as e:
        print(f"Google token verification or DB save failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid Google token or DB error")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.post("/api/feature-request")
async def submit_feature_request(request: FeatureRequest):
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feature_requests (user_email, feature_text) VALUES (%s, %s)",
                (request.user_email, request.feature_text)
            )
            conn.commit()
        return {"message": "Feature request submitted successfully."}
    except Exception as e:
        print(f"Feature request insert error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error saving feature request.")
    finally:
        if conn:
            conn.close()




