# backend/main.py

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
# Import for Together AI
from dotenv import load_dotenv
from together import Together
from together.error import AuthenticationError # Import the error from its correct submodule

# --- Load environment variables from .env file ---
load_dotenv()

# --- Securely load API Key ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# --- Add this for debugging ---
if TOGETHER_API_KEY:
    print(f"DEBUG: API Key loaded successfully, starting with '{TOGETHER_API_KEY[:4]}...'.")
else:
    print("DEBUG: API Key was NOT loaded. Check your backend/.env file.")

client = Together(api_key=TOGETHER_API_KEY)

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:5173",  # Assuming your frontend runs on this port
    # Add other origins if needed
]

# This block has been correctly indented
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

    if not user_prompt:
        raise HTTPException(status_code=400, detail="User prompt is required for problem generation.")

    try:
        # Construct a more specific prompt for the LLM
        system_message = (
            "You are an expert-level AI physics and mathematics tutor. Your primary audience is students preparing for the IIT-JEE (Mains and Advanced) competitive exams in India. "
            "Your task is to generate a single, challenging, and non-trivial practice problem based on the user's request. "
            "The problem must be of 'JEE Advanced' difficulty, often requiring the synthesis of multiple concepts. "
            "Do NOT generate simple, textbook-style, or single-concept questions. Assume the user is highly intelligent and is looking for a challenge. "
            "Output ONLY the problem statement. Do not provide any hints, solutions, or explanations."
        )
        # Pass the user's prompt directly for a cleaner request.
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
