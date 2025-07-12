# backend/main.py

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pypdf import PdfReader
import uuid # For generating unique filenames
import shutil # For saving uploaded files temporarily
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
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
UPLOAD_DIR = "uploaded_syllabi"
EXTRACTED_TEXT_DIR = "extracted_syllabi_text"

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACTED_TEXT_DIR, exist_ok=True)

# --- PDF Extraction Utility Function ---
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a single PDF file."""
    try:
        with open(pdf_path, "rb") as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        raise

# --- FastAPI Endpoint for Syllabus Upload ---
@app.post("/upload-syllabus/")
async def upload_syllabus(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    syllabus_id = str(uuid.uuid4())
    
    pdf_save_path = os.path.join(UPLOAD_DIR, f"{syllabus_id}.pdf")
    text_save_path = os.path.join(EXTRACTED_TEXT_DIR, f"{syllabus_id}.txt")

    try:
        # Save the uploaded PDF file temporarily
        with open(pdf_save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract text from the saved PDF
        extracted_text = extract_text_from_pdf(pdf_save_path)

        # Save the extracted text to a .txt file
        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        return JSONResponse(content={
            "message": "Syllabus uploaded and processed successfully!",
            "syllabus_id": syllabus_id,
            "filename": file.filename,
            "extracted_text_path": text_save_path # For debugging/demonstration
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        print(f"An error occurred during syllabus upload or processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process syllabus: {e}")
    finally:
        # Clean up the temporary uploaded PDF file if you don't need to keep it
        if os.path.exists(pdf_save_path):
            os.remove(pdf_save_path)

# --- NEW FastAPI Endpoint to Get Syllabus Text by ID ---
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

# --- Optional: Basic Root Endpoint to check if backend is running ---
@app.get("/")
async def read_root():
    return {"message": "FastAPI Backend for AI Tutor is running!"}