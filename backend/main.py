# backend/main.py

import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
import uuid # For generating unique filenames
import shutil # For saving uploaded files temporarily
import io # For handling file in memory

# Import for Together AI
import together # UNCOMMENTED

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
UPLOAD_DIR = "uploaded_syllabi" # This folder is for temporary PDF storage, often cleaned up
EXTRACTED_TEXT_DIR = "extracted_syllabi_text" # This folder stores the extracted text

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACTED_TEXT_DIR, exist_ok=True)

# --- PDF Extraction Utility Function ---
# Modified to accept UploadFile directly, for cleaner handling
def extract_text_from_pdf(pdf_file: UploadFile) -> str:
    """Extracts text from a single PDF file from an UploadFile object."""
    try:
        # Read the file content into a BytesIO object
        file_content = pdf_file.file.read()
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_file.filename}: {e}")
        raise

# --- FastAPI Endpoint for Syllabus Upload ---
@app.post("/upload-syllabus/")
async def upload_syllabus(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    syllabus_id = str(uuid.uuid4())
    
    # We will save the extracted text directly, no need to save the PDF permanently
    # pdf_save_path = os.path.join(UPLOAD_DIR, f"{syllabus_id}.pdf") # No longer needed for permanent storage
    text_save_path = os.path.join(EXTRACTED_TEXT_DIR, f"{syllabus_id}.txt")

    try:
        # Extract text directly from the UploadFile
        extracted_text = extract_text_from_pdf(file)

        # Save the extracted text to a .txt file
        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        return JSONResponse(content={
            "message": "Syllabus uploaded and processed successfully!",
            "syllabus_id": syllabus_id,
            "filename": file.filename,
            "extracted_text_path": text_save_path # For debugging/demonstration
        }, status_code=200)

    except Exception as e:
        print(f"An error occurred during syllabus upload or processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process syllabus: {e}")

# --- FastAPI Endpoint to Get Syllabus Text by ID ---
@app.get("/get-syllabus-text/{syllabus_id}")
async def get_syllabus_text(syllabus_id: str):
    """
    Retrieves the extracted text of a syllabus by its unique ID.
    """
    text_file_path = os.path.join(EXTRACTED_TEXT_DIR, f"{syllabus_id}.txt")

    if not os.path.exists(text_file_path):
        raise HTTPException(status_code=404, detail="Syllabus text not found.")

    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            syllabus_text = f.read()
        return JSONResponse(content={"syllabus_text": syllabus_text}, status_code=200)
    except Exception as e:
        print(f"Error reading syllabus text for ID {syllabus_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve syllabus text.")

# --- NEW ENDPOINT: LLM Problem Generation ---
@app.post("/generate-llm-problem")
async def generate_llm_problem(request: Request):
    data = await request.json()
    prompt = data.get("prompt")

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required for problem generation.")

    try:
        # --- YOUR TOGETHER AI INTEGRATION LOGIC GOES HERE ---
        # 1. Ensure you have the 'together' Python library installed: pip install together
        # 2. Set your Together AI API key directly here (less secure but works for testing):
        together.api_key = "20e2ca95bb5ae5aa0c9663c628e65804411fe49518eea9db767cc230ff768867" # <<<--- REPLACE THIS WITH YOUR ACTUAL KEY
        #    OR (recommended for production): Set it as an environment variable:
        #    os.environ["TOGETHER_API_KEY"] = "YOUR_TOGETHER_API_KEY_HERE"
        #    or simply ensure it's set in your shell before starting uvicorn:
        #    export TOGETHER_API_KEY="your_key" (Linux/macOS)
        #    set TOGETHER_API_KEY=your_key (Windows CMD)


        # Call Together AI
        response = together.chat.completions.create(
            model="meta-llama/Llama-3-8b-chat-hf", # You can choose another model here
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500, # Adjust as needed
            temperature=0.7, # Adjust creativity
        )
        generated_text = response.choices[0].message.content # This extracts the text from the response

        # The placeholder line is now fully removed or commented out
        # generated_text = f"Problem generated by backend (Together AI integration pending): {prompt}"

        return JSONResponse(
            status_code=200,
            content={"generated_text": generated_text}
        )
    except Exception as e:
        print(f"Error in LLM problem generation endpoint: {e}") # Log the error on the backend
        # Return a more informative error to the frontend if possible
        raise HTTPException(status_code=500, detail=f"Failed to generate problem via LLM. Backend error: {e}")

# --- Optional: Basic Root Endpoint to check if backend is running ---
@app.get("/")
async def read_root():
    return {"message": "FastAPI Backend for AI Tutor is running!"}