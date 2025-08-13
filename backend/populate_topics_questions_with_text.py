import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
from pdf2image import convert_from_path
import pytesseract
import glob  # For flexible PDF search

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

# --- Comprehensive Name Mapping (expanded for mismatches) ---
NAME_MAPPING = {
    # ... (your full list here; add variations if needed, e.g.)
    'Kinetic Theory': 'Kinetic-Theory',
    'Laws Of Motion': 'Laws-Of-Motion',
    'Continuity And Differentiability': 'Continuity And Differentiability',
    # Add more as needed for skipped chapters
}

# Appendix chapters to skip (as per your note)
APPENDIX_CHAPTERS = ['Infinite Series', 'Proofs In Mathematics']

def log(msg: str):
    print(msg, flush=True)

def get_chapter_map_from_db(cursor):
    cursor.execute("SELECT name, id FROM chapters")
    return {name: chapter_id for name, chapter_id in cursor.fetchall()}

def clean_ocr_text(text: str, subject: str) -> str:
    text = re.sub(r'[^\S\r\n]+', ' ', text)  # Multiple spaces to single
    text = re.sub(r'\s*\n\s*', '\n', text)   # Normalize newlines
    if 'physics' in subject.lower():
        text = re.sub(r'(\d+)\s*[\.=:\-]\s*(\d+)', r'\1.\2', text)  # Fix "2=1", "2 : 1" to "2.1"
        text = re.sub(r'\[\s*(\d+)\s*\]', r'\1', text)  # Clean equation artifacts
    text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)  # Comma in numbers to dot
    return text.strip()

def find_pdf_path(folder_path, pdf_filename):
    # Try exact match first
    pdf_path = os.path.join(folder_path, pdf_filename)
    if os.path.exists(pdf_path):
        return pdf_path
    # Flexible search: ignore case, hyphens, spaces
    search_pattern = os.path.join(folder_path, pdf_filename.replace('-', '?').replace(' ', '?') + '.*')  # ? for optional char
    matches = glob.glob(search_pattern, recursive=False)
    if matches:
        log(f"    [INFO] Found matching PDF: {matches[0]} (instead of {pdf_filename})")
        return matches[0]
    return None

def get_text_from_pdf_with_caching(pdf_path: str, subject: str) -> str:
    pdf_filename = os.path.basename(pdf_path)
    cache_filepath = os.path.join(OCR_CACHE_FOLDER, pdf_filename + ".txt")

    if os.path.exists(cache_filepath):
        log(f"    - Found cached OCR text for '{pdf_filename}'. Reading from cache.")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()

    log("    - No cache found. Converting PDF to images and running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=400 if 'physics' in subject.lower() else 300, poppler_path=POPPLER_PATH)
        full_text = ""
        config = '--psm 3'  # Default
        if 'physics' in subject.lower():
            config = '--psm 4'  # Better for diagrams
        for i, image in enumerate(images):
            full_text += pytesseract.image_to_string(image, config=config) + "\n"
        log("    - OCR complete.")
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        log(f"    - Saved new OCR text to cache: '{os.path.basename(cache_filepath)}'")
        return full_text
    except Exception as e:
        log(f"    [ERROR] OCR process failed for {pdf_filename}: {e}")
        return ""

def extract_topics(ocr_text: str, topics_from_csv: pd.DataFrame):
    extracted_topics = []
    
    # Normalize CSV headings: Strip commas for matching
    topics_from_csv['heading_text_normalized'] = topics_from_csv['heading_text'].str.replace(',', '', regex=False)
    
    # Enhanced regex: Very flexible for artifacts
    topic_numbers_escaped = [re.escape(str(num)).replace('\\.', r'(?:[\.\s:\-,;])?') for num in topics_from_csv['heading_number']]
    heading_pattern = re.compile(r'(?m)^\s*(' + '|'.join(topic_numbers_escaped) + r')(?:\s*[\.\s:\-,;]?|$)', re.IGNORECASE | re.DOTALL)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {}
    text_length = len(ocr_text)
    for match in matches:
        cleaned_num = re.sub(r'[\s:\-,;]+', '.', match.group(1)).strip('.')
        pos = match.start()
        if pos < text_length * 0.8 and cleaned_num not in topic_locations:
            topic_locations[cleaned_num] = pos
            log(f"    - Matched heading: {cleaned_num} at position {pos}")

    # Log expected vs found
    expected_topics = set(topics_from_csv['heading_number'].astype(str))
    found_topics = set(topic_locations.keys())
    missing_topics = expected_topics - found_topics
    log(f"    - Found {len(topic_locations)} of {len(topics_from_csv)} topic headings in the PDF text.")
    if missing_topics:
        log(f"    - Missing topics: {', '.join(sorted(missing_topics))} (check OCR for artifacts or adjust regex).")
        for miss in list(missing_topics)[:3]:
            miss_pos = ocr_text.find(miss)
            if miss_pos != -1:
                snippet = ocr_text[max(0, miss_pos-50):miss_pos+50].replace('\n', ' ')
                log(f"      - Snippet around missing '{miss}': ...{snippet}...")

    # Extract content
    sorted_locations = sorted(topic_locations.items(), key=lambda x: x[1])
    for i, (topic_num, start_pos) in enumerate(sorted_locations):
        end_pos = sorted_locations[i+1][1] if i+1 < len(sorted_locations) else text_length
        content = ocr_text[start_pos:end_pos].strip()
        row = topics_from_csv[topics_from_csv['heading_number'] == topic_num]
        title = row['heading_text'].values[0] if not row.empty else ''
        extracted_topics.append({'topic_number': topic_num, 'title': title, 'content': content})

    # Even stronger fallback: Looser pattern, scan multiple times if needed
    loose_pattern = re.compile(r'(?m)(?:^|\n)\s*(\d+(?:[\.\s,\-;:]\d+)?(?:[\.\s,\-;:]\d+)?)\s*[\.:;]?\s*', re.IGNORECASE)
    for _ in range(2):  # Scan twice for deeper nesting
        for topic in extracted_topics[:]:
            content = topic['content']
            sub_matches = loose_pattern.finditer(content)
            for sub_match in sub_matches:
                sub_cleaned = re.sub(r'[\s,\-;:]+', '.', sub_match.group(1)).strip('.')
                if sub_cleaned in missing_topics and sub_cleaned not in topic_locations:
                    sub_start = sub_match.start() + topic_locations[topic['topic_number']]
                    topic_locations[sub_cleaned] = sub_start
                    sub_end = text_length
                    for next_num, next_pos in sorted_locations:
                        if next_pos > sub_start:
                            sub_end = next_pos
                            break
                    sub_content = ocr_text[sub_start:sub_end].strip()
                    sub_row = topics_from_csv[topics_from_csv['heading_number'] == sub_cleaned]
                    sub_title = sub_row['heading_text'].values[0] if not sub_row.empty else ''
                    extracted_topics.append({'topic_number': sub_cleaned, 'title': sub_title, 'content': sub_content})
                    log(f"    - Fallback match for subtopic: {sub_cleaned} at position {sub_start}")
                    missing_topics.remove(sub_cleaned)

    return extracted_topics

def update_database(cursor, chapter_id: int, topics: list):
    log(f"    - Preparing to update {len(topics)} topics in the database.")
    for topic in topics:
        cursor.execute("UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s", (topic['content'], chapter_id, topic['topic_number']))
    log(f"    - Database update commands sent.")

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
    processed_chapters_count = 0
    skipped_chapters_count = 0

    cursor.execute("""
        SELECT c.id, c.name, c.class_number, s.name as subject_name_db
        FROM chapters c
        JOIN subjects s ON c.subject_id = s.id
        ORDER BY s.name, c.class_number, c.name
    """)
    db_chapters = cursor.fetchall()

    for chapter_id, chapter_name_db, class_number, subject_name_db in db_chapters:
        if any(app in chapter_name_db for app in APPENDIX_CHAPTERS):
            log(f"    [INFO] Skipping appendix chapter '{chapter_name_db}'.")
            skipped_chapters_count += 1
            continue
        
        log(f"\n--- Processing Chapter: {chapter_name_db} ({subject_name_db} Class {class_number}) ---")
        folder_subject = 'Maths' if subject_name_db == 'Mathematics' else subject_name_db
        mapped_pdf_filename_base = NAME_MAPPING.get(chapter_name_db, chapter_name_db)
        pdf_filename = f"{mapped_pdf_filename_base}.pdf"
        class_folder = f"Class {class_number}"
        folder_path = os.path.join(PDF_ROOT_FOLDER, folder_subject, class_folder)
        
        pdf_path = find_pdf_path(folder_path, pdf_filename)  # Flexible search
        if not pdf_path:
            log(f"    [WARNING] PDF not found for '{chapter_name_db}' (tried variations). Skipping chapter.")
            skipped_chapters_count += 1
            continue

        chapter_topics_df = master_df[master_df['chapter_file'] == pdf_filename].copy()
        if chapter_topics_df.empty:
            log(f"    [WARNING] No topics found in CSV for chapter '{pdf_filename}'. Skipping.")
            skipped_chapters_count += 1
            continue

        full_chapter_text = get_text_from_pdf_with_caching(pdf_path, subject_name_db)
        if not full_chapter_text:
            log(f"    [ERROR] Failed to get text from '{pdf_filename}'. Skipping.")
            skipped_chapters_count += 1
            continue
        
        full_chapter_text = clean_ocr_text(full_chapter_text, subject_name_db)
        topics_data = extract_topics(full_chapter_text, chapter_topics_df)
        
        if not topics_data:
            log(f"    [WARNING] No topics extracted from text. Skipping database update.")
        else:
            update_database(cursor, chapter_id, topics_data)
            conn.commit()
            log(f"    [SUCCESS] Finished processing and saving data for '{chapter_name_db}' (updated {len(topics_data)} topics).")
            processed_chapters_count += 1

    cursor.close()
    conn.close()
    log(f"\n[COMPLETE] Script finished. Processed {processed_chapters_count} chapters, skipped {skipped_chapters_count} chapters.")

if __name__ == '__main__':
    main()
