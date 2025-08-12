import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
import psycopg2

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def extract_full_text_from_pdf(pdf_path):
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

    # Get subjects dictionary {id: name}
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    # All chapters needing text (full_text IS NULL)
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters WHERE full_text IS NULL")
    chapters_to_process = cursor.fetchall()
    
    if not chapters_to_process:
        print("[INFO] All chapters already have their full text. Nothing to do.")
        conn.close()
        return

    print(f"[INFO] Found {len(chapters_to_process)} chapters that need their full text populated.")

    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id)
        if not subject_name:
            print(f"  [WARNING] Could not find subject with ID {subject_id} for '{chapter_name}'. Skipping.")
            continue

        # Compose folder and filename (matches your Windows path convention)
        class_folder = f"Class {class_number}"
        # Remove hyphens for compatibility, if you use spaces in filenames
        file_name = f"{chapter_name.replace('-', ' ')}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_folder, file_name)
        print(f"\nProcessing Chapter ID {chapter_id}: {chapter_name}")
        print(f"  [DEBUG] Trying PDF path: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found at '{pdf_path}'. Skipping.")
            continue

        full_text = extract_full_text_from_pdf(pdf_path)

        if full_text:
            # Update chapters table directly
            cursor.execute(
                "UPDATE chapters SET full_text = %s WHERE id = %s",
                (full_text, chapter_id)
            )
            print(f"  [SUCCESS] Updated chapter '{chapter_name}' with its full text.")

    conn.commit()
    cursor.close()
    conn.close()
    print("\n[COMPLETE] Finished populating chapter text in chapters table.")

if __name__ == '__main__':
    main()
