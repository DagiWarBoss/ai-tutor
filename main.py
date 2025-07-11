# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os

from src.generate_questions import generate_practice_problem

app = FastAPI()

# --- FIX: Update CORS Configuration ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",  # <--- ADD THIS LINE (or whatever port your React app is actually running on)
    # If you deploy your frontend, add its domain here, e.g., "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------------------

class ProblemRequest(BaseModel):
    subject: str
    grade: str
    topic: str
    syllabus_text: str = ""

class ProblemResponse(BaseModel):
    problem: str

@app.get("/")
async def read_root():
    return {"message": "AI Tutor Backend is running!"}

@app.post("/generate_problem", response_model=ProblemResponse)
async def get_practice_problem(request: ProblemRequest):
    print(f"Received request to generate problem for: {request.subject}, {request.grade}, {request.topic}")
    try:
        problem = generate_practice_problem(
            request.subject,
            request.grade,
            request.topic,
            request.syllabus_text
        )
        if "Could not generate problem" in problem:
            raise HTTPException(status_code=500, detail=f"Failed to generate problem: {problem}")
        return {"problem": problem}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in /generate_problem endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during problem generation on the server: {e}")