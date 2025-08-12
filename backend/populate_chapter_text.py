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

    # 2. Find all chapters that are MISSING full_text
    cursor.execute("SELECT id, name, class_number, subject_id, chapter_number FROM chapters WHERE full_text IS NULL")
    chapters_to_process = cursor.fetchall()
    
    if not chapters_to_process:
        print("[INFO] All chapters already have their full text populated. Nothing to do.")
        conn.close()
        return

    print(f"[INFO] Found {len(chapters_to_process)} chapters that need their full text extracted.")

    # 3. Loop through each chapter, extract its text, and update chapters table
    for chapter_id, chapter_name, class_number, subject_id, chapter_number in chapters_to_process:
        subject_name = subjects.get(subject_id)
        if not subject_name:
            print(f"  [WARNING] Could not find subject with ID {subject_id} for chapter '{chapter_name}'. Skipping.")
            continue
            
        # Handle special chapter_number (e.g., 'A1' -> 69, optional from earlier discussion)
        if isinstance(chapter_number, str) and chapter_number.startswith('A'):
            print(f"  [INFO] Special appendix detected for '{chapter_name}'; handling as chapter_number 69.")
            # You can add update logic here if needed, e.g., cursor.execute("UPDATE chapters SET chapter_number = 69 WHERE id = %s", (chapter_id,))

        pdf_filename = f"{chapter_name.replace('-', ' ')}.pdf"  # Normalize hyphens to spaces
        class_folder = f"Class {class_number}"
        folder_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_folder)
        pdf_path = os.path.join(folder_path, pdf_filename)
        
        print(f"\nProcessing Chapter ID {chapter_id}: {chapter_name}")
        print(f"  [DEBUG] Chapter name from DB: '{chapter_name}'")
        print(f"  [DEBUG] Expected file name: '{pdf_filename}'")
        print(f"  [DEBUG] Trying PDF path: {pdf_path}")
        
        if os.path.exists(folder_path):
            print(f"  [DEBUG] Files in directory: {os.listdir(folder_path)}")
        else:
            print(f"  [WARNING] Folder not found: '{folder_path}'. Skipping.")
            continue

        if not os.path.exists(pdf_path):
            # Fuzzy match fallback: Find file containing key words from chapter_name
            chapter_base = chapter_name.replace('-', ' ').lower()
            candidates = [f for f in os.listdir(folder_path) if chapter_base in f.lower() and f.endswith('.pdf')]
            if candidates:
                pdf_path = os.path.join(folder_path, candidates[0])
                print(f"  [INFO] Using fuzzy match: Found and using '{candidates[0]}'")
            else:
                print(f"  [WARNING] No matching PDF found for '{chapter_name}' (tried fuzzy match). Skipping.")
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
