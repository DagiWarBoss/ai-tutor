import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
from dataclasses import dataclass, field
from typing import List


# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai--tutor\backend\NCERT_PCM_ChapterWise"
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


def log(msg: str):
    print(msg, flush=True)


def normalize_name(name: str) -> str:
    """Creates a consistent, searchable key from a name by removing all non-alphanumeric characters, handling diacritics implicitly, and making it lowercase."""
    # This strips punctuation, spaces, hyphens, commas, etc., and lowers case
    return re.sub(r'[^a-z0-9]', '', name.lower())


@dataclass
class TextBlock:
    text: str; page: int; y: float


@dataclass
class TopicAnchor:
    topic_number: str; title: str; page: int; y: float
    content: str = field(default="")


def get_text_from_pdf_with_caching(pdf_path: str) -> str:
    pdf_filename = os.path.basename(pdf_path)
    cache_filepath = os.path.join(OCR_CACHE_FOLDER, pdf_filename + ".txt")
    if os.path.exists(cache_filepath):
        log(f"  - Reading from cache: '{pdf_filename}'")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()
    log(f"  - No cache found for '{pdf_filename}'. Running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
        full_text = "".join(pytesseract.image_to_string(img) + "\n" for img in images)
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        log("  - OCR complete and text cached.")
        return full_text
    except Exception as e:
        log(f"  [ERROR] OCR process failed for {pdf_filename}: {e}")
        return ""


def extract_all_text_blocks(doc_text: str) -> List[TextBlock]:
    """Converts raw OCR text into a list of located text blocks."""
    all_blocks = []
    for i, line in enumerate(doc_text.split('\n')):
        if line.strip():
            all_blocks.append(TextBlock(text=line.strip(), page=0, y=float(i)))
    return all_blocks


def find_anchor_locations(topics_from_csv: pd.DataFrame, all_blocks: List[TextBlock]) -> List[TopicAnchor]:
    """Uses fuzzy matching with partial ratio on normalized text to find topic locations, handling variations like extra words, punctuation, or slight spelling differences."""
    from rapidfuzz import process, fuzz
    anchors = []
    block_texts = [block.text for block in all_blocks]
    normalized_block_texts = [normalize_name(text) for text in block_texts]
    
    for _, row in topics_from_csv.iterrows():
        topic_num = str(row['heading_number'])
        topic_title = str(row['heading_text'])
        search_query = f"{topic_num} {topic_title}"
        normalized_query = normalize_name(search_query)
        best_match = process.extractOne(normalized_query, normalized_block_texts, scorer=fuzz.partial_ratio, score_cutoff=85)
        
        if best_match:
            match_text, score, index = best_match
            found_block = all_blocks[index]
            log(f"  [ANCHOR FOUND] {topic_num} {topic_title} (Score: {score:.0f})")
            anchors.append(TopicAnchor(topic_number=topic_num, title=topic_title, page=found_block.page, y=found_block.y))
        else:
            log(f"  [ANCHOR FAILED] Could not find: {topic_num} {topic_title}")


    anchors.sort(key=lambda a: (a.page, a.y))
    return list({(a.page, a.y): a for a in anchors}.values())


def assign_content_to_anchors(anchors: List[TopicAnchor], all_blocks: List[TextBlock]):
    """Assigns all text that appears between two anchors to the first anchor."""
    for i, current_anchor in enumerate(anchors):
        content_blocks = []
        start_y = current_anchor.y
        end_y = anchors[i+1].y if i + 1 < len(anchors) else float('inf')
        for block in all_blocks:
            if start_y < block.y < end_y:
                content_blocks.append(block.text)
        current_anchor.content = "\n".join(content_blocks).strip()
    return anchors


def extract_questions(ocr_text: str) -> List[dict]:
    questions = []
    exercises_match = re.search(r'EXERCISES', ocr_text, re.IGNORECASE)
    if exercises_match:
        exercises_text = ocr_text[exercises_match.start():]
        question_pattern = re.compile(r'(\d+\.\d+)\s+(.+?)(?=\n\d+\.\d+|\Z)', re.DOTALL)
        found_questions = question_pattern.findall(exercises_text)
        for q_num, q_text in found_questions:
            questions.append({'question_number': q_num, 'question_text': q_text.strip()})
    return questions


def update_database(cursor, chapter_id: int, topics: List[TopicAnchor], questions: list):
    """Updates the database."""
    log(f"  - Updating {len(topics)} topics and {len(questions)} questions.")
    for topic in topics:
        if topic.content:
            cursor.execute("UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                           (topic.content, chapter_id, topic.topic_number))
    if questions:
        cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
        for q in questions:
            cursor.execute("INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
                           (chapter_id, q['question_number'], q['question_text']))
    log(f"  - Database updates complete.")


def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        log("[INFO] Connected to Supabase.")
    except Exception as e:
        log(f"[ERROR] Connection failed: {e}")
        return
        
    try:
        master_df = pd.read_csv(CSV_PATH, dtype=str).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        log(f"[INFO] Loaded master topic list from {CSV_PATH}.")
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {CSV_PATH}")
        return


    cursor.execute("SELECT name, id FROM chapters")
    db_chapters = {normalize_name(name): chap_id for name, chap_id in cursor.fetchall()}


    csv_chapters = master_df[['subject', 'class', 'chapter_file']].drop_duplicates().to_dict('records')


    for chapter_info in csv_chapters:
        pdf_filename = chapter_info['chapter_file']
        chapter_name = os.path.splitext(pdf_filename)[0]
        
        log(f"\n--- Processing: {pdf_filename} ---")
        
        chapter_id = db_chapters.get(normalize_name(chapter_name))
        if not chapter_id:
            log(f"  [WARNING] Chapter '{chapter_name}' not found in DB. Skipping.")
            continue
            
        pdf_path = os.path.join(PDF_ROOT_FOLDER, chapter_info['subject'], chapter_info['class'], pdf_filename)
        if not os.path.exists(pdf_path):
            log(f"  [WARNING] PDF file not found at '{pdf_path}'. Skipping.")
            continue
            
        chapter_topics_df = master_df[master_df['chapter_file'] == pdf_filename]
        
        ocr_text = get_text_from_pdf_with_caching(pdf_path)
        if ocr_text:
            all_blocks = extract_all_text_blocks(ocr_text)
            anchors = find_anchor_locations(chapter_topics_df, all_blocks)
            topics_with_content = assign_content_to_anchors(anchors, all_blocks)
            questions = extract_questions(ocr_text)
            
            update_database(cursor, chapter_id, topics_with_content, questions)
            conn.commit()
            log(f"  [SUCCESS] Saved data for '{chapter_name}'.")


    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")


if __name__ == '__main__':
    main()
