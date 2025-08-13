import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract
import pandas as pd

# ======= VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def log(msg: str):
    print(msg, flush=True)

def normalize_name(name: str) -> str:
    """Creates a consistent, searchable key from a name."""
    return re.sub(r'[\s\-_]', '', name.lower())

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
    extracted_topics = []
    topic_numbers = sorted(topics_from_csv['heading_number'].tolist(), key=lambda x: [int(i) for i in x.split('.')])
    heading_pattern = re.compile(r'^\s*(%s)\s+' % '|'.join([re.escape(tn) for tn in topic_numbers]), re.MULTILINE)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {match.group(1).strip(): match.start() for match in matches}

    for index, row in topics_from_csv.iterrows():
        topic_num = str(row['heading_number'])
        start_pos = topic_locations.get(topic_num)
        if start_pos is not None:
            end_pos = len(ocr_text)
            for next_num, next_pos in topic_locations.items():
                if next_pos > start_pos and next_pos < end_pos:
                    end_pos = next_pos
            content = ocr_text[start_pos:end_pos].strip()
            title = content.split('\n')[0].strip()
            extracted_topics.append({'topic_number': topic_num, 'title': title, 'content': content})

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
    for topic in topics:
        cursor.execute("UPDATE topics SET full_text = %s, name = %s WHERE chapter_id = %s AND topic_number = %s",
                       (topic['content'], topic['title'], chapter_id, topic['topic_number']))
    cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
    for q in questions:
        cursor.execute("INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
                       (chapter_id, q['question_number'], q['question_text']))
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

    # Create a normalized map of chapters from the database
    cursor.execute("SELECT name, id FROM chapters")
    db_chapter_map = {normalize_name(name): chapter_id for name, chapter_id in cursor.fetchall()}

    # Get a unique list of chapters from the CSV, our source of truth
    csv_chapters = master_df[['subject', 'class', 'chapter_file']].drop_duplicates().to_dict('records')

    log(f"[INFO] Found {len(csv_chapters)} unique chapters in the CSV to process.")

    for chapter_info in csv_chapters:
        csv_filename = chapter_info['chapter_file']
        csv_chapter_name = os.path.splitext(csv_filename)[0]
        
        log(f"\n--- Processing: {csv_filename} ---")
        
        # Find the chapter in the database using the normalized name
        normalized_name = normalize_name(csv_chapter_name)
        chapter_id = db_chapter_map.get(normalized_name)
        
        if not chapter_id:
            log(f"  [WARNING] Chapter '{csv_chapter_name}' not found in the database using normalized name. Skipping.")
            continue
            
        # Find the actual PDF file path
        pdf_path = os.path.join(PDF_ROOT_FOLDER, chapter_info['subject'], chapter_info['class'], csv_filename)
        if not os.path.exists(pdf_path):
            log(f"  [WARNING] PDF file not found at '{pdf_path}'. Skipping.")
            continue
        
        # Filter the master CSV for this specific chapter
        chapter_topics_df = master_df[master_df['chapter_file'] == csv_filename]

        ocr_text = run_ocr_on_pdf(pdf_path)
        if ocr_text:
            topics, questions = extract_topics_and_questions(ocr_text, chapter_topics_df)
            log(f"  - Extracted {len(topics)} topics and {len(questions)} questions.")
            update_database(cursor, chapter_id, topics, questions)
            conn.commit()
            log(f"  [SUCCESS] Saved data for '{csv_chapter_name}' to Supabase.")

    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")

if __name__ == '__main__':
    main()