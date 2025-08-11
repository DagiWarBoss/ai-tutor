import os
import re
import csv
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv

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

def load_topics_from_csv(csv_path: str, chapter_file: str) -> List[Tuple[str, str]]:
    """Loads the ground-truth list of topics for a specific chapter from the master CSV."""
    topics = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("chapter_file") == chapter_file:
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

def find_anchors_by_number(topics_from_csv: List[Tuple[str, str]], all_blocks: List[TextBlock]) -> List[TopicAnchor]:
    """
    --- NEW "NUMBER-FIRST" LOGIC ---
    Finds topic locations by matching the topic NUMBER first.
    """
    anchors = []
    
    # Create a map of all text blocks that look like topic numbers
    number_block_map: Dict[str, TextBlock] = {}
    topic_num_pattern = re.compile(r"^\d{1,2}(\.\d{1,2})*$")
    for block in all_blocks:
        # Check if the block's text is a plausible topic number
        if topic_num_pattern.match(block.text):
            number_block_map[block.text] = block

    # For each topic from our trusted CSV, find its corresponding number block
    for topic_num, topic_title in topics_from_csv:
        if topic_num in number_block_map:
            found_block = number_block_map[topic_num]
            log(f"  [ANCHOR] Found number '{topic_num}' on page {found_block.page + 1}")
            anchors.append(TopicAnchor(topic_number=topic_num, title=topic_title, page=found_block.page, y=found_block.y))
        else:
            log(f"  [ANCHOR-FAIL] Could not find block for number: {topic_num} ('{topic_title}')")

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
        
        # Also, check if the title is in the first block after the number
        if content_blocks:
            first_content_block = content_blocks[0].lower()
            topic_title_cleaned = re.sub(r'[^a-z0-9\s]', '', current_anchor.title.lower())
            if topic_title_cleaned in first_content_block:
                # Remove the title itself from the content
                content_blocks[0] = content_blocks[0].replace(current_anchor.title, "").strip()

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
        
        topics_from_csv = load_topics_from_csv(CSV_PATH, pdf_filename)
        if not topics_from_csv:
            log(f"  [WARNING] No topics found in CSV for '{pdf_filename}'. Skipping.")
            continue
            
        doc = fitz.open(pdf_path)
        all_text_blocks = extract_all_text_blocks(doc)
        doc.close()
        
        anchors = find_anchors_by_number(topics_from_csv, all_text_blocks)
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