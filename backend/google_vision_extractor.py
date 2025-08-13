import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
from google.cloud import vision
import io

# ======= 1. THIS PATH HAS BEEN CORRECTED =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
# Assumes GOOGLE_APPLICATION_CREDENTIALS is set in your .env file
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

def log(msg: str):
    print(msg, flush=True)

def get_chapter_map_from_db(cursor):
    """Fetches all chapters from the DB to create a name-to-ID map."""
    cursor.execute("SELECT name, id FROM chapters")
    return {name: chapter_id for name, chapter_id in cursor.fetchall()}

def run_google_ocr_on_pdf(pdf_path: str) -> str:
    """Performs OCR on a PDF using the Google Cloud Vision API."""
    log("  - Sending PDF to Google Cloud Vision API for OCR...")
    try:
        client = vision.ImageAnnotatorClient()
        with io.open(pdf_path, 'rb') as pdf_file:
            content = pdf_file.read()

        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        input_config = vision.InputConfig(content=content, mime_type='application/pdf')
        request = vision.AnnotateFileRequest(features=[feature], input_config=input_config)
        
        response = client.batch_annotate_files(requests=[request])
        
        full_text = ""
        for image_response in response.responses[0].responses:
            full_text += image_response.full_text_annotation.text + "\n"
        
        log("  - OCR complete.")
        return full_text
    except Exception as e:
        log(f"  [ERROR] Google Cloud Vision API process failed for {os.path.basename(pdf_path)}: {e}")
        return ""

def get_text_from_pdf_with_caching(pdf_path: str) -> str:
    """Uses Google Cloud Vision for OCR and caches the result."""
    pdf_filename = os.path.basename(pdf_path)
    cache_filepath = os.path.join(OCR_CACHE_FOLDER, pdf_filename + ".txt")
    
    if os.path.exists(cache_filepath):
        log(f"  - Reading from cache: '{pdf_filename}'")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()

    full_text = run_google_ocr_on_pdf(pdf_path)
    if full_text:
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        log(f"  - Saved new OCR text to cache for '{pdf_filename}'")
    return full_text

def extract_topics_and_questions(ocr_text: str, topics_from_csv: pd.DataFrame):
    """Extracts topics and questions from the clean OCR text."""
    extracted_topics, questions = [], []
    
    topic_numbers = sorted(topics_from_csv['heading_number'].tolist(), key=lambda x: [int(i) for i in x.split('.')])
    heading_pattern = re.compile(r'^\s*(%s)\s+' % '|'.join([re.escape(tn) for tn in topic_numbers]), re.MULTILINE)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {match.group(1).strip(): match.start() for match in matches}

    for topic_num in topic_numbers:
        start_pos = topic_locations.get(topic_num)
        if start_pos is not None:
            end_pos = len(ocr_text)
            for next_num, next_pos in topic_locations.items():
                if next_pos > start_pos and next_pos < end_pos:
                    end_pos = next_pos
            content = ocr_text[start_pos:end_pos].strip()
            title = content.split('\n')[0].strip()
            extracted_topics.append({'topic_number': topic_num, 'title': title, 'content': content})

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

    chapter_map = get_chapter_map_from_db(cursor)
    all_pdf_paths = [os.path.join(root, filename) for root, _, files in os.walk(PDF_ROOT_FOLDER) for filename in files if filename.lower().endswith('.pdf')]
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

        ocr_text = get_text_from_pdf_with_caching(pdf_path)
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