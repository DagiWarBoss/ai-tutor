import os
import sys
import traceback
import random
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

from agentic import router as agentic_router  # Added import for Agentic Study Room routes
from aiquickhelp import router as aiquickhelp_router  # Import your new Quick AI Help router

# --- DEBUG: Print environment variables containing sensitive info keys ---
print("---- ENVIRONMENT VARIABLES ----")
for key, value in os.environ.items():
    if "DB" in key or "API" in key or "SUPABASE" in key:
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

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("DB config loaded:", DB_HOST, DB_USER, DB_NAME, DB_PORT)
print("Supabase URL and Service Key loaded.")  # Avoid printing keys for security

# Initialize AI and Embedding clients
llm_client = Together(api_key=TOGETHER_API_KEY)
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"Error loading embedding model: {e}")
    traceback.print_exc()
    sys.exit(1)

# Initialize Supabase client
from supabase import create_client, Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Request Models
class ContentRequest(BaseModel):
    topic: str
    mode: str

class GoogleLoginRequest(BaseModel):
    token: str

class FeatureRequest(BaseModel):
    user_email: str
    feature_text: str

app = FastAPI()

# Register Agentic Study Room API routes
app.include_router(agentic_router, prefix="/agentic", tags=["Agentic Study Room"])

# Register Quick AI Help API routes
app.include_router(aiquickhelp_router, prefix="/agentic", tags=["Agentic Quick Help"])

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
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Explicit OPTIONS handler for all routes to assist CORS preflight requests ===
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

# Helper functions for Supabase conversation messages storage
def insert_message(user_id: str, conversation_id: str, role: str, message: str):
    supabase.table("conversation_messages").insert({
        "user_id": user_id,
        "conversation_id": conversation_id,
        "role": role,
        "message": message
    }).execute()

def get_recent_messages(conversation_id: str, limit: int = 10):   # Changed limit to 10 as requested
    response = supabase.table("conversation_messages") \
                      .select("role, message") \
                      .eq("conversation_id", conversation_id) \
                      .order("created_at", desc=True) \
                      .limit(limit) \
                      .execute()
    # Return messages in chronological order
    return response.data[::-1] if response.data else []

# Your existing routes and code below...

# Together.ai request method remains unchanged
async def call_together_ai_api(prompt: str, max_new_tokens: int = 256) -> str:
    if not TOGETHER_API_KEY:
        raise HTTPException(status_code=500, detail="Together.ai API key not configured")

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.7,
            "max_new_tokens": max_new_tokens,
            "stop": ["\n"]
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.together.ai/api/llm/mixtral-8x7b-instruct-v0.1", headers=headers, json=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"LLM API call failed: {response.text}")

    data = response.json()
    return data.get("generated_text") or data.get("output") or "<No response>"

# Updated chat endpoint using Supabase persistent storage with 10 messages history
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation_id = f"conv_{request.user_id}"

    # Retrieve last 10 messages for the prompt context
    history = get_recent_messages(conversation_id, limit=10)
    history_text = "\n".join([f"{m['role'].capitalize()}: {m['message']}" for m in history])

    prompt = f"Conversation history:\n{history_text}\nUser: {request.message}\nAI:"

    reply_text = await call_together_ai_api(prompt, max_new_tokens=256)

    # Store user and AI messages persistently
    insert_message(request.user_id, conversation_id, "user", request.message)
    insert_message(request.user_id, conversation_id, "ai", reply_text)

    return ChatResponse(reply=reply_text.strip(), conversation_id=conversation_id, timestamp=datetime.utcnow().isoformat())



