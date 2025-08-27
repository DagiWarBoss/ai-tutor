import psycopg2
import traceback
import random
import json
import re
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer
from together import Together
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from dotenv import load_dotenv
import os

# Load environment variables inside this module
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Config from env (ensure these are set in .env)
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# Initialize clients
llm_client = Together(api_key=TOGETHER_API_KEY)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

router = APIRouter()

def get_db_connection():
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        return conn
    except psycopg2.OperationalError as e:
        print(f"DB connection error: {e}")
        traceback.print_exc()
        return None

def parse_quiz_json_from_string(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^``````|```
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            question_match = re.search(r'"question":\s*"(.*?)"', text, re.DOTALL)
            options_match = re.search(r'"options":\s*{(.*?)}', text, re.DOTALL)
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
            print(f"Regex parsing error: {e}")
            traceback.print_exc()
            return None

@router.get("/status")
async def status():
    return {"message": "Agentic Study Room API is running"}

@router.post("/api/generate-content")
async def generate_content(request: BaseModel):
    topic_prompt = request.topic
    mode = request.mode
    conn = None
    try:
        topic_embedding = embedding_model.encode(topic_prompt).tolist()
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        relevant_text, context_level, context_name = "", "", ""
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 10)", (topic_embedding,))
            match_results = cur.fetchall()
            if not match_results:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": topic_prompt, "source_level": "User Query"})
            # Select random matched topic
            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = random.choice(match_results)
            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()
            if topic_text_result and topic_text_result and topic_text_result.strip():
                relevant_text, context_level, context_name = topic_text_result, "Topic", matched_topic_name
            else:
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                if chapter_text_result and chapter_text_result and chapter_text_result.strip():[9]
                    relevant_text, context_level, context_name = chapter_text_result, "Chapter", chapter_text_result[9]
                else:
                    return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": matched_topic_name, "source_level": "Topic"})
        if mode == "practice" and context_level == "Chapter":
            if context_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": context_name, "source_level": context_level})
        max_chars = 15000
        if len(relevant_text) > max_chars:
            relevant_text = relevant_text[:max_chars]
        user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
        system_message = ""
        if mode == 'revise':
            system_message = "You are an AI assistant creating a structured 'cheat sheet' for JEE topics."
        elif mode == 'practice':
            system_message = ("You are an expert AI quiz generator for JEE students. "
                "Given textbook context, respond ONLY with a valid JSON object matching this template: "
                '{"question": "...", "options": { "A": "...", "B": "...", "C": "...", "D": "..." }, "correct_answer": "...", "explanation": "..."}.'
                "Do not include any explanations or markdown. ONLY output strict JSON.")
        else:
            system_message = "You are an expert JEE tutor."
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4, "messages": messages}
        response = llm_client.chat.completions.create(**response_params)
        content = response.choices.message.content.strip()
        if not content or content.lower().startswith(("i'm sorry", "i cannot")):
            raise HTTPException(status_code=503, detail="The AI was unable to generate a response.")
        if mode == 'practice':
            parsed_quiz = parse_quiz_json_from_string(content)
            if not parsed_quiz:
                raise HTTPException(status_code=502, detail="The AI returned invalid format.")
            parsed_quiz['source_name'] = context_name
            parsed_quiz['source_level'] = context_level
            return JSONResponse(content=parsed_quiz)
        else:
            return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
    finally:
        if conn:
            conn.close()

@router.post("/api/google-login")
async def google_login(data: BaseModel):
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            "621306164868-21bamnrurup0nk6f836fss6q92s04aav.apps.googleusercontent.com"
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
        return {"email": email, "name": name}
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@router.post("/api/feature-request")
async def submit_feature_request(request: BaseModel):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feature_requests (user_email, feature_text) VALUES (%s, %s)",
                (request.user_email, request.feature_text)
            )
            conn.commit()
        return {"message": "Feature request submitted successfully."}
    finally:
        conn.close()





