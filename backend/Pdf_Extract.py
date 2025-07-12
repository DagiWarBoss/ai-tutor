# api_backend/main.py (or your chosen backend file name)

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pypdf import PdfReader # PyPDF2 is now pypdf
import uuid # For generating unique filenames
import shutil # For saving uploaded files temporarily

# Initialize FastAPI app
app = FastAPI()

# --- Configuration ---
# ✅ Base directory for uploaded syllabi and extracted text
# This should ideally be outside your direct source code, e.g., a 'data' folder
# For demonstration, we'll place it relative to this script.
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

    # Generate a unique ID for this upload
    syllabus_id = str(uuid.uuid4())
    
    # Define paths for the uploaded PDF and the extracted text
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
        
        # In a real application, you'd store metadata (syllabus_id, original_filename, etc.)
        # in a database here. For now, we'll just return the ID and a message.

        return JSONResponse(content={
            "message": "Syllabus uploaded and processed successfully!",
            "syllabus_id": syllabus_id,
            "filename": file.filename,
            "extracted_text_path": text_save_path # For debugging/demonstration
        }, status_code=200)

    except HTTPException: # Re-raise FastAPI's own HTTPExceptions
        raise
    except Exception as e:
        print(f"An error occurred during syllabus upload or processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process syllabus: {e}")
    finally:
        # Clean up the temporary uploaded PDF file if you don't need to keep it
        # For long-term storage, you might move it to permanent storage or S3
        if os.path.exists(pdf_save_path):
            os.remove(pdf_save_path) # Remove the uploaded PDF after processing