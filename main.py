# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os # Import os to potentially handle environment variables for ports etc.

# --- IMPORTANT: Import your problem generation function ---
# This import assumes main.py is in the root and src/generate_questions.py exists.
# If your structure changes, you might need to adjust this.
from src.generate_questions import generate_practice_problem

app = FastAPI()

# --- CORS Configuration (Crucial for React Frontend) ---
# Your React app will typically run on http://localhost:3000 during development.
# Add your specific frontend URL(s) here.
origins = [
    "http://localhost:3000",
    # If you deploy your frontend, add its domain here, e.g., "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],    # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],    # Allows all headers
)
# --------------------------------------------------------

# Define the request body structure for problem generation
class ProblemRequest(BaseModel):
    subject: str
    grade: str
    topic: str
    syllabus_text: str = "" # Optional: for passing specific syllabus text

# Define the response body structure (optional but good practice)
class ProblemResponse(BaseModel):
    problem: str

@app.get("/")
async def read_root():
    """Basic endpoint to check if the FastAPI server is running."""
    return {"message": "AI Tutor Backend is running!"}

@app.post("/generate_problem", response_model=ProblemResponse)
async def get_practice_problem(request: ProblemRequest):
    """
    Endpoint to generate a practice problem using Together AI.
    Receives subject, grade, topic, and optional syllabus text.
    """
    print(f"Received request to generate problem for: {request.subject}, {request.grade}, {request.topic}")
    try:
        # Call your problem generation function
        problem = generate_practice_problem(
            request.subject,
            request.grade,
            request.topic,
            request.syllabus_text
        )
        if "Could not generate problem" in problem: # Check for error messages from generate_questions.py
            raise HTTPException(status_code=500, detail=f"Failed to generate problem: {problem}")
        return {"problem": problem}
    except HTTPException as e:
        # Re-raise HTTPExceptions (e.g., from an API key issue caught in generate_questions.py)
        raise e
    except Exception as e:
        # Catch any other unexpected errors and return a 500 status
        print(f"Error in /generate_problem endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during problem generation on the server: {e}")

# You can add more endpoints here for other functionalities (e.g., login, syllabus upload, dashboard data)