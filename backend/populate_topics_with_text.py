import os
import re
import csv
from dataclasses import dataclass, field
from typing import List, Tuple
import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv
from rapidfuzz import fuzz

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def log(msg: str):
    print(msg, flush=True)

@dataclass
class TextBlock:
    text: str
    page: int
    y: float

@dataclass
class TopicAnchor:
    topic_number: str
    title: str
    page: int
    y: float
    content: str = field(default="")

def load_topics_from_csv(csv_path: str, chapter_file: str, subject: str, class_name: str) -> List[Tuple[str, str]]:
    """Loads the ground-truth list of topics for a specific chapter from the master CSV."""
    topics = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("chapter_file", "").strip() == chapter_file.strip() and
                    row.get("subject", "").strip() == subject.strip() and
                    row.get("class", "").strip() == class_name.strip()):
                    topics.append((row["heading_number"], row["heading_text"]))
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {csv_path}")
    
    topics.sort(key=lambda t: [int(x) for x in t[0].split(".") if x.isdigit()])
    return topics

def extract_all_text_blocks(doc: fitz.Document) -> List[TextBlock]:
    """Extracts all text blocks from a PDF with their locations, filtering headers/footers."""
    all_blocks = []
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        top_margin, bottom_margin = page_height * 0.10, page_height * 0.90
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            x0, y0, x1, y1, block_text_raw, _, _ = b
            if y0 < top_margin or y1 > bottom_margin: continue
            text = block_text_raw.strip().replace('\n', ' ')
            if text:
                all_blocks.append(TextBlock(text=text, page=page_num, y=y0))
    return all_blocks

def find_anchors_by_searching_csv_topics(topics_from_csv: List[Tuple[str, str]], all_blocks: List[TextBlock]) -> List[TopicAnchor]:
    """Finds topic locations by directly searching for the number and title from the CSV."""
    anchors = []
    for topic_num, topic_title in topics_from_csv:
        best_block = None
        highest_score = 0
        
        # Search all text blocks for the best match
        for block in all_blocks:
            # Condition 1: Must start with the correct topic number
            if block.text.strip().startswith(topic_num):
                # Condition 2: Use fuzzy matching to see how well the title matches
                # This is robust against small OCR errors or extra words
                score = fuzz.partial_ratio(topic_title.lower(), block.text.lower())
                if score > highest_score:
                    highest_score = score
                    best_block = block
        
        # If we found a good enough match, create an anchor
        if highest_score > 80: # Using a high threshold for confidence
            log(f"  [ANCHOR FOUND] {topic_num} {topic_title} (Score: {highest_score})")
            anchors.append(TopicAnchor(topic_number=topic_num, title=topic_title, page=best_block.page, y=best_block.y))
        else:
            log(f"  [ANCHOR FAILED] Could not find: {topic_num} {topic_title}")

    anchors.sort(key=lambda a: (a.page, a.y))
    return anchors

def assign_content_to_anchors(anchors: List[TopicAnchor], all_blocks: List[TextBlock]):
    """Assigns all text that appears between two anchors to the first anchor."""
    for i, current_anchor in enumerate(anchors):
        content_blocks = []
        start_page, start_y = current_anchor.page, current_anchor.y
        end_page = anchors[i+1].page if i + 1 < len(anchors) else float('inf')
        end_y = anchors[i+1].y if i + 1 < len(anchors) else float('inf')

        for block in all_blocks:
            is_after_start = block.page > start_page or (block.page == start_page and block.y > start_y)
            is_before_end = block.page < end_page or (block.page == end_page and block.y < end_y)
            if is_after_start and is_before_end:
                content_blocks.append(block.text)
        
        current_anchor.content = "\n".join(content_blocks).strip()
    return anchors

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        log(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
    chapters_in_db = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects_map = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    for chapter_id, chapter_name, class_number, subject_id in chapters_in_db:
        subject_name = subjects_map.get(subject_id)
        if not subject_name: continue

        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
        
        log(f"\n--- Processing: {pdf_filename} ---")
        if not os.path.exists(pdf_path):
            log(f"  [WARNING] PDF file not found. Skipping.")
            continue
        
        topics_from_csv = load_topics_from_csv(CSV_PATH, pdf_filename, subject_name, class_name)
        if not topics_from_csv:
            log(f"  [WARNING] No topics found in CSV for this specific chapter. Skipping.")
            continue
            
        doc = fitz.open(pdf_path)
        all_text_blocks = extract_all_text_blocks(doc)
        doc.close()
        
        anchors = find_anchors_by_searching_csv_topics(topics_from_csv, all_text_blocks)
        topics_with_content = assign_content_to_anchors(anchors, all_text_blocks)
        
        update_count = 0
        for topic in topics_with_content:
            if topic.content:
                cursor.execute(
                    "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                    (topic.content, chapter_id, topic.topic_number)
                )
                update_count += 1
        
        if update_count > 0:
            conn.commit()
        log(f"  [SUCCESS] Updated {update_count} of {len(topics_from_csv)} topics for this chapter.")
    
    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")

if __name__ == '__main__':
    main()