# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os

# --- IMPORTANT: Import your problem generation function ---
# Changed to import the new function that returns both problem and solution
from src.generate_questions import generate_problem_and_solution

app = FastAPI()

# --- CORS Configuration (Crucial for React Frontend) ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",  # Your React app runs here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------------------

# Define the request body structure for problem generation
class ProblemRequest(BaseModel):
    subject: str
    grade: str
    topic: str
    syllabus_text: str = "" # Optional: for passing specific syllabus text

# Define the response body structure (NOW INCLUDES SOLUTION)
class ProblemResponse(BaseModel):
    problem: str
    solution: str # New field for the solution

@app.get("/")
async def read_root():
    """Basic endpoint to check if the FastAPI server is running."""
    return {"message": "AI Tutor Backend is running!"}

@app.post("/generate_problem", response_model=ProblemResponse)
async def get_practice_problem(request: ProblemRequest):
    """
    Endpoint to generate a practice problem and its solution using Together AI.
    Receives subject, grade, topic, and optional syllabus text.
    """
    print(f"Received request to generate problem for: {request.subject}, {request.grade}, {request.topic}")
    try:
        # Call your problem generation function (now returns both)
        problem, solution = generate_problem_and_solution(
            request.subject,
            request.grade,
            request.topic,
            request.syllabus_text
        )
        if "Could not generate problem" in problem or "Could not generate solution" in solution:
            raise HTTPException(status_code=500, detail=f"Failed to generate problem/solution.")

        return {"problem": problem, "solution": solution} # Return both
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in /generate_problem endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during problem/solution generation on the server: {e}")