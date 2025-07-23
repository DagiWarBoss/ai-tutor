# backend/main.py

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
# Import for Together AI
from dotenv import load_dotenv
from together import Together, AuthenticationError # Use the modern client and import specific error

# --- Load environment variables from .env file ---
load_dotenv()

# --- Securely load API Key ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# --- Add this for debugging ---
if TOGETHER_API_KEY:
    print(f"DEBUG: API Key loaded successfully, starting with '{TOGETHER_API_KEY[:4]}...'.")
else:
    print("DEBUG: API Key was NOT loaded. Check your backend/.env file.")

if not TOGETHER_API_KEY:
    print("FATAL ERROR: TOGETHER_API_KEY environment variable not set.")
    # In a real app, you might exit or have a fallback.
    # For development, this print statement is a clear indicator.

client = Together(api_key=TOGETHER_API_KEY)

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:5173",  # Your frontend's URL/port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SIMPLIFIED ENDPOINT: LLM Problem Generation ---
@app.post("/generate-llm-problem")
async def generate_llm_problem(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt")
    # Expect the full syllabus text directly, not an ID
    syllabus_content = data.get("syllabusText", "") # Default to empty string

    if not user_prompt:
        raise HTTPException(status_code=400, detail="User prompt is required for problem generation.")

    try:
        # Construct a more specific prompt for the LLM using the modern chat format
        system_message = "You are an AI tutor. Your task is to generate a single, concise practice problem based on the user's request. Do NOT provide a solution or any explanation. Only output the problem statement."
        user_message_content = f"Generate a {user_prompt} problem."

        if syllabus_content:
            user_message_content += f"\n\nStrictly adhere to the following syllabus context:\n```\n{syllabus_content}\n```"

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

# --- Optional: Basic Root Endpoint to check if backend is running ---
@app.get("/")
async def read_root():
    return {"message": "FastAPI Backend for AI Tutor is running!"}
