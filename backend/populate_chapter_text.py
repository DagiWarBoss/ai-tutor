import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
import psycopg2

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def extract_full_text_from_pdf(pdf_path):
    """
    Opens a PDF file and extracts its entire text content page by page.
    """
    print(f"    - Reading file: {os.path.basename(pdf_path)}")
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
        return full_text
    except Exception as e:
        print(f"    [WARNING] Could not extract text from {os.path.basename(pdf_path)}: {e}")
        return None

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file.")
        return
        
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    # 1. Get all subjects to help build file paths
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    # 2. Find all chapters that are MISSING their full_text content
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters WHERE full_text IS NULL")
    chapters_to_process = cursor.fetchall()
    
    if not chapters_to_process:
        print("[INFO] All chapters already have their full text populated. Nothing to do.")
        conn.close()
        return

    print(f"[INFO] Found {len(chapters_to_process)} chapters that need their full text extracted.")

    # 3. Loop through each chapter, extract its text, and update the database
    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id)
        if not subject_name:
            print(f"  [WARNING] Could not find subject with ID {subject_id} for chapter '{chapter_name}'. Skipping.")
            continue
            
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
        
        print(f"\nProcessing Chapter ID {chapter_id}: {chapter_name}")

        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found at '{pdf_path}'. Skipping.")
            continue
            
        # Extract the full text from the corresponding PDF
        full_text = extract_full_text_from_pdf(pdf_path)
        
        if full_text:
            # Update the chapter row in the database with the full text
            cursor.execute(
                "UPDATE chapters SET full_text = %s WHERE id = %s",
                (full_text, chapter_id)
            )
            print(f"  [SUCCESS] Successfully updated chapter '{chapter_name}' with its full text.")

    # 4. Commit all changes to the database
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n[COMPLETE] Finished populating chapter text.")

if __name__ == '__main__':
    main()