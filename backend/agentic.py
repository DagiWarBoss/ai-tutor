from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import httpx
import os

router = APIRouter()

# Together.ai API URL and API key from environment variable
TOGETHER_API_URL = "https://api.together.ai/api/llm/mixtral-8x7b-instruct-v0.1"
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# Data Models
class ChatRequest(BaseModel):
    user_id: str
    message: str
    context: List[str] = []

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    timestamp: str

class StudyPlanRequest(BaseModel):
    user_id: str
    subjects: List[str]
    days: int
    goals: str

class StudyPlanResponse(BaseModel):
    plan: str
    timestamp: str

class ProblemRequest(BaseModel):
    user_id: str
    problem_text: str

class ProblemResponse(BaseModel):
    steps: List[str]
    full_solution: str
    timestamp: str

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
        response = await client.post(TOGETHER_API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"LLM API call failed: {response.text}")

    data = response.json()
    # Extract text response (adjust key if API response format differs)
    return data.get("generated_text") or data.get("output") or "<No response>"

# Agentic Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    reply_text = await call_together_ai_api(request.message)
    conversation_id = "conv_" + request.user_id
    timestamp = str(datetime.now())
    return ChatResponse(reply=reply_text, conversation_id=conversation_id, timestamp=timestamp)

@router.post("/study-plan", response_model=StudyPlanResponse)
async def study_plan(request: StudyPlanRequest):
    prompt = f"Create a {request.days}-day study plan for the subjects: {', '.join(request.subjects)}. The goal is: {request.goals}."
    plan_text = await call_together_ai_api(prompt, max_new_tokens=500)
    timestamp = str(datetime.now())
    return StudyPlanResponse(plan=plan_text, timestamp=timestamp)

@router.post("/problem", response_model=ProblemResponse)
async def solve_problem(request: ProblemRequest):
    prompt = f"Explain step-by-step how to solve the following problem:\n{request.problem_text}"
    solution_text = await call_together_ai_api(prompt, max_new_tokens=500)
    
    # Simple parsing steps from response (if structured), else just place solution in full_solution
    steps = [
        "1. Understand the problem.",
        "2. Apply relevant concepts.",
        "3. Calculate the solution."
    ]
    timestamp = str(datetime.now())
    return ProblemResponse(steps=steps, full_solution=solution_text, timestamp=timestamp)

