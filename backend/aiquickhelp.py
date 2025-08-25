import os
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
TOGETHER_API_URL = "https://api.together.ai/api/llm/mixtral-8x7b-instruct-v0.1"

class QuickHelpRequest(BaseModel):
    subject: str
    chapter: str
    topic: str
    query: str

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"DB connection error: {e}")
        traceback.print_exc()
        return None

def fetch_syllabus_content(subject: str, chapter: str, topic: str) -> Optional[str]:
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # Fetch topic content first
            cur.execute("""
                SELECT full_text FROM topics
                WHERE name = %s
                LIMIT 1
            """, (topic,))
            topic_row = cur.fetchone()
            if topic_row and topic_row.get("full_text"):
                return topic_row["full_text"]
            # Fallback to chapter content
            cur.execute("""
                SELECT full_text FROM chapters
                WHERE name = %s
                LIMIT 1
            """, (chapter,))
            chapter_row = cur.fetchone()
            if chapter_row and chapter_row.get("full_text"):
                return chapter_row["full_text"]
        return None
    except Exception as e:
        print(f"Error fetching syllabus content: {e}")
        traceback.print_exc()
        return None
    finally:
        conn.close()

def construct_prompt(context: str, user_query: str) -> str:
    return (
        "You are a highly knowledgeable AI tutor specialized for JEE preparation.\n"
        "For all quick help requests—including special exceptions in chemistry concepts, derivations of physics formulas, \n"
        "and unique archetypes of math questions—this Quick Help endpoint is exclusively responsible.\n"
        "Provide thorough, detailed, and well-explained answers without limiting the length to ensure full understanding.\n"
        "Use ONLY the syllabus content provided below as your factual basis.\n"
        "If relevant, format your response with markdown tables, diagrams, and examples suitable for educational use.\n\n"
        "SYLLABUS CONTENT:\n"
        f"{context}\n\n"
        "STUDENT QUESTION:\n"
        f"{user_query}"
    )

async def call_together_ai(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.4,
            "max_new_tokens": 1024,  # Increased token limit for more detailed answers
            "top_p": 0.9,
            "stop": []
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(TOGETHER_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data.get("generated_text", "")

@router.post("/quick-help")
async def quick_help(req: QuickHelpRequest):
    try:
        context = fetch_syllabus_content(req.subject, req.chapter, req.topic)
        if not context:
            raise HTTPException(status_code=404, detail="No syllabus content found for the specified topic or chapter.")
        prompt = construct_prompt(context, req.query)
        answer = await call_together_ai(prompt)
        if not answer.strip() or answer.lower().startswith(("i'm sorry", "i cannot", "i don't know")):
            raise HTTPException(status_code=503, detail="AI was unable to generate a response.")
        return {"answer": answer}
    except httpx.HTTPError as api_error:
        print(f"LLM API error: {api_error}")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Error communicating with AI API.")
    except Exception as e:
        print(f"Unexpected error in quick-help: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error.")
