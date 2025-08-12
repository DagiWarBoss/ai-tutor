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

    # 2. Find all chapters that are MISSING an entry in chapter_texts
    cursor.execute("""
        SELECT c.id, c.name, c.class_number, c.subject_id 
        FROM chapters c 
        LEFT JOIN chapter_texts ct ON c.id = ct.chapter_id 
        WHERE ct.id IS NULL
    """)
    chapters_to_process = cursor.fetchall()
    
    if not chapters_to_process:
        print("[INFO] All chapters already have their full text populated in chapter_texts. Nothing to do.")
        conn.close()
        return

    print(f"[INFO] Found {len(chapters_to_process)} chapters that need their full text extracted.")

    # 3. Loop through each chapter, extract its text, and insert into chapter_texts
    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id)
        if not subject_name:
            print(f"  [WARNING] Could not find subject with ID {subject_id} for chapter '{chapter_name}'. Skipping.")
            continue
            
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, str(class_number), pdf_filename)
        
        print(f"\nProcessing Chapter ID {chapter_id}: {chapter_name}")

        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found at '{pdf_path}'. Skipping.")
            continue
            
        # Extract the full text from the corresponding PDF
        full_text = extract_full_text_from_pdf(pdf_path)
        
        if full_text:
            # Insert into the new chapter_texts table
            cursor.execute(
                "INSERT INTO chapter_texts (chapter_id, full_text) VALUES (%s, %s)",
                (chapter_id, full_text)
            )
            print(f"  [SUCCESS] Successfully inserted full text for chapter '{chapter_name}' into chapter_texts.")

    # 4. Commit all changes to the database
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n[COMPLETE] Finished populating chapter text in chapter_texts table.")

if __name__ == '__main__':
    main()
