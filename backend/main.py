# backend/main.py

import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
import uuid # For generating unique filenames
import shutil # For saving uploaded files temporarily
import io # For handling file in memory
import json # Import json for parsing the response

# Import for Together AI
import together # Make sure you have installed: pip install together

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

# --- Configuration ---
# UPLOAD_DIR is no longer strictly needed for temporary PDF storage,
# as we'll process in memory, but kept for consistency if you save other files.
UPLOAD_DIR = "uploaded_syllabi"
EXTRACTED_TEXT_DIR = "extracted_syllabi_text" # This folder stores the extracted text

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True) # Still create if other uses
os.makedirs(EXTRACTED_TEXT_DIR, exist_ok=True)

# --- PDF Extraction Utility Function (MODIFIED) ---
# This function now directly accepts an UploadFile object.
def extract_text_from_pdf(pdf_file: UploadFile) -> str:
    """Extracts text from a single PDF file from an UploadFile object."""
    try:
        # Read the file content into a BytesIO object
        # Use pdf_file.file.read() to get the bytes content
        reader = PdfReader(io.BytesIO(pdf_file.file.read()))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_file.filename}: {e}")
        raise

# --- FastAPI Endpoint for Syllabus Upload (MODIFIED) ---
@app.post("/upload-syllabus/")
async def upload_syllabus(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    syllabus_id = str(uuid.uuid4())
    text_save_path = os.path.join(EXTRACTED_TEXT_DIR, f"{syllabus_id}.txt")

    try:
        # Extract text directly from the UploadFile object (MODIFIED)
        extracted_text = extract_text_from_pdf(file)

        # Save the extracted text to a .txt file
        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        return JSONResponse(content={
            "message": "Syllabus uploaded and processed successfully!",
            "syllabus_id": syllabus_id,
            "filename": file.filename,
            "extracted_text_path": text_save_path
        }, status_code=200)

    except Exception as e:
        print(f"An error occurred during syllabus upload or processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process syllabus: {e}")

# --- NEW HELPER FUNCTION to get raw syllabus text ---
async def get_syllabus_content_by_id(syllabus_id: str) -> str:
    text_file_path = os.path.join(EXTRACTED_TEXT_DIR, f"{syllabus_id}.txt")
    if not os.path.exists(text_file_path):
        return "" # Return empty string if not found, let LLM handle no context
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading syllabus text for ID {syllabus_id}: {e}")
        return "" # Return empty string on error

@app.get("/get-syllabus-text/{syllabus_id}")
async def get_syllabus_text_endpoint(syllabus_id: str): # Renamed to avoid clash with helper
    """
    Retrieves the extracted text of a syllabus by its unique ID for API consumers.
    """
    syllabus_text = await get_syllabus_content_by_id(syllabus_id) # Use the helper
    if not syllabus_text:
        raise HTTPException(status_code=404, detail="Syllabus text not found or error occurred.")
    return JSONResponse(content={"syllabus_text": syllabus_text}, status_code=200)

# --- MODIFIED ENDPOINT: LLM Problem Generation ---
@app.post("/generate-llm-problem")
async def generate_llm_problem(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt") # Rename 'prompt' to 'user_prompt' for clarity
    syllabus_id = data.get("syllabusId") # Expect syllabusId separately from frontend

    if not user_prompt:
        raise HTTPException(status_code=400, detail="User prompt is required for problem generation.")

    syllabus_content = ""
    if syllabus_id:
        try:
            syllabus_content = await get_syllabus_content_by_id(syllabus_id)
            if not syllabus_content:
                print(f"No syllabus content found for ID {syllabus_id}. Generating without specific context.")
        except Exception as e:
            print(f"Error fetching syllabus content for ID {syllabus_id}: {e}. Generating without specific context.")
            syllabus_content = "" # Ensure it's empty on error

    try:
        together.api_key = "YOUR_TOGETHER_API_KEY_HERE" # <<<--- REPLACE THIS WITH YOUR ACTUAL KEY

        # Construct a more specific prompt for the LLM
        system_message = "You are an AI tutor. Your task is to generate a single, concise practice problem. Do NOT provide a solution. Do NOT repeat the input prompt or syllabus content in your response."
        
        if syllabus_content:
            llm_prompt_content = f"{system_message}\n\nBased on the following syllabus content, generate a {user_prompt} problem:\n\nSyllabus:\n```\n{syllabus_content}\n```\n\nPractice Problem:"
        else:
            llm_prompt_content = f"{system_message}\n\nGenerate a {user_prompt} problem. No specific syllabus context was provided."

        # For Llama-3-8b-chat-hf and similar models on Together AI, the chat completion API
        # is generally preferred, but since you had issues with `together.chat`,
        # we stick to `Completion.create` but use the specific Llama-3 instruction format.
        formatted_llm_prompt = (
            f"<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n"
            f"{system_message}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n"
            f"{llm_prompt_content}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n"
        )

        response = together.Completion.create(
            model="meta-llama/Llama-3-8b-chat-hf",
            prompt=formatted_llm_prompt,
            max_tokens=500,
            temperature=0.7,
            stop=["<|eot_id|>", "<|end_of_text|>"] # Stop generation at these tokens
        )
        
        generated_text = response.choices[0].text

        # Clean up any leftover instruction tokens if the model somehow includes them
        generated_text = generated_text.replace("[/INST]", "").replace("[INST]", "").strip()
        generated_text = generated_text.replace("<|eot_id|>", "").replace("<|end_of_text|>", "").strip()
        generated_text = generated_text.replace("<|start_header_id|>assistant<|end_header_id|>", "").strip()
        generated_text = generated_text.replace("<|start_header_id|>user<|end_header_id|>", "").strip()
        generated_text = generated_text.replace("<|start_header_id|>system<|end_header_id|>", "").strip()
        generated_text = generated_text.replace("<|begin_of_text|>", "").strip()


        return JSONResponse(
            status_code=200,
            content={"generated_text": generated_text}
        )
    except Exception as e:
        print(f"Error in LLM problem generation endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate problem via LLM. Backend error: {e}")

# --- Optional: Basic Root Endpoint to check if backend is running ---
@app.get("/")
async def read_root():
    return {"message": "FastAPI Backend for AI Tutor is running!"}