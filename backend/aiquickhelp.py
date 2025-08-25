import os
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from together import Together

router = APIRouter()

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
llm_client = Together(api_key=TOGETHER_API_KEY)

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
            # Try fetching topic content
            cur.execute("""
                SELECT full_text FROM topics WHERE name = %s LIMIT 1
            """, (topic,))
            row = cur.fetchone()
            if row and row.get("full_text"):
                return row["full_text"]
            # Fallback to chapter content
            cur.execute("""
                SELECT full_text FROM chapters WHERE name = %s LIMIT 1
            """, (chapter,))
            row = cur.fetchone()
            if row and row.get("full_text"):
                return row["full_text"]
        return None
    except Exception as e:
        print(f"Error retrieving syllabus content: {e}")
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

@router.post("/quick-help")
async def quick_help(req: QuickHelpRequest):
    try:
        context = fetch_syllabus_content(req.subject, req.chapter, req.topic)
        if not context:
            raise HTTPException(status_code=404, detail="No syllabus content found for the specified topic or chapter.")
        prompt = construct_prompt(context, req.query)
        response_params = {
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "temperature": 0.4,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": "You are a helpful AI tutor."},
                {"role": "user", "content": prompt},
            ],
        }
        response = await llm_client.chat.completions.create(**response_params)
        answer = response.choices[0].message.content.strip()
        if not answer or answer.lower().startswith(("i'm sorry", "i cannot", "i don't know")):
            raise HTTPException(status_code=503, detail="AI was unable to generate a response.")
        return {"answer": answer}
    except Exception as e:
        print(f"Error in Quick Help endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error.")

