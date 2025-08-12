import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract
import pandas as pd

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def log(msg: str):
    print(msg, flush=True)

def get_chapter_map_from_db(cursor):
    """Fetches all chapters from the DB to create a name-to-ID map."""
    cursor.execute("SELECT name, id FROM chapters")
    return {name: chapter_id for name, chapter_id in cursor.fetchall()}

def run_ocr_on_pdf(pdf_path: str) -> str:
    """Performs OCR on every page of a PDF and returns the full text."""
    log("  - Converting PDF to images and running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
        full_text = ""
        for i, image in enumerate(images):
            full_text += pytesseract.image_to_string(image) + "\n"
        log("  - OCR complete.")
        return full_text
    except Exception as e:
        log(f"  [ERROR] OCR process failed for {os.path.basename(pdf_path)}: {e}")
        return ""

def extract_topics_and_questions(ocr_text: str, topics_from_csv: pd.DataFrame):
    """
    --- NEW, SIMPLIFIED LOGIC ---
    Extracts both topics and questions using a reliable split-based method.
    """
    extracted_topics = []
    
    # Get a sorted list of topic numbers from the trusted CSV
    topic_numbers = sorted(topics_from_csv['heading_number'].tolist(), key=lambda x: [int(i) for i in x.split('.')])
    
    # Create a regex pattern to find all topic numbers in the text
    # This pattern looks for the start of a line, then a number, then whitespace
    heading_pattern = re.compile(r'^\s*(%s)\s+' % '|'.join([re.escape(tn) for tn in topic_numbers]), re.MULTILINE)
    matches = list(heading_pattern.finditer(ocr_text))
    
    topic_locations = {match.group(1).strip(): match.start() for match in matches}

    for topic_num in topic_numbers:
        start_pos = topic_locations.get(topic_num)
        if start_pos is not None:
            # Find the start position of the next topic to define the end of this topic's content
            end_pos = len(ocr_text)
            for next_num, next_pos in topic_locations.items():
                # Check if next_pos is a valid end point (after start_pos)
                if next_pos > start_pos and next_pos < end_pos:
                    end_pos = next_pos
            
            content = ocr_text[start_pos:end_pos].strip()
            # The title is the first line of the content
            title = content.split('\n')[0].strip()
            
            extracted_topics.append({
                'topic_number': topic_num,
                'title': title,
                'content': content
            })

    # Extract questions (using the same reliable logic as before)
    questions = []
    exercises_match = re.search(r'EXERCISES', ocr_text, re.IGNORECASE)
    if exercises_match:
        exercises_text = ocr_text[exercises_match.start():]
        question_pattern = re.compile(r'(\d+\.\d+)\s+(.+?)(?=\n\d+\.\d+|\Z)', re.DOTALL)
        found_questions = question_pattern.findall(exercises_text)
        for q_num, q_text in found_questions:
            questions.append({'question_number': q_num, 'question_text': q_text.strip()})
            
    return extracted_topics, questions

def update_database(cursor, chapter_id: int, topics: list, questions: list):
    """Updates the database with the extracted topics and questions."""
    log(f"  - Preparing to update {len(topics)} topics and {len(questions)} questions.")
    # Update topics
    for topic in topics:
        cursor.execute(
            "UPDATE topics SET full_text = %s, name = %s WHERE chapter_id = %s AND topic_number = %s",
            (topic['content'], topic['title'], chapter_id, topic['topic_number'])
        )
    # Update questions (delete old ones first)
    cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
    for q in questions:
        cursor.execute(
            "INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
            (chapter_id, q['question_number'], q['question_text'])
        )
    log(f"  - Database update commands sent.")

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        log("[INFO] Successfully connected to Supabase.")
    except Exception as e:
        log(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    try:
        master_df = pd.read_csv(CSV_PATH, dtype=str).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        log(f"[INFO] Loaded master topic list from {CSV_PATH}.")
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {CSV_PATH}")
        return

    chapter_map = get_chapter_map_from_db(cursor)

    all_pdf_paths = []
    for root, dirs, files in os.walk(PDF_ROOT_FOLDER):
        for filename in files:
            if filename.lower().endswith('.pdf'):
                all_pdf_paths.append(os.path.join(root, filename))
    all_pdf_paths.sort()
    
    log(f"[INFO] Found {len(all_pdf_paths)} PDF files to process.")

    for pdf_path in all_pdf_paths:
        filename = os.path.basename(pdf_path)
        chapter_name = os.path.splitext(filename)[0]
        
        log(f"\n--- Processing: {filename} ---")
        
        chapter_id = chapter_map.get(chapter_name)
        if not chapter_id:
            log(f"  [WARNING] Chapter '{chapter_name}' not found in the database. Skipping.")
            continue
        
        chapter_topics_df = master_df[master_df['chapter_file'] == filename]
        if chapter_topics_df.empty:
            log(f"  [WARNING] No topics for this chapter in the CSV. Skipping.")
            continue

        ocr_text = run_ocr_on_pdf(pdf_path)
        if ocr_text:
            topics, questions = extract_topics_and_questions(ocr_text, chapter_topics_df)
            log(f"  - Extracted {len(topics)} topics and {len(questions)} questions.")
            update_database(cursor, chapter_id, topics, questions)
            conn.commit()
            log(f"  [SUCCESS] Saved data for '{chapter_name}' to Supabase.")

    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")

if __name__ == '__main__':
    main()