import os
import re
import csv
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv
from rapidfuzz import process, fuzz

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
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["chapter_file"] == chapter_file:
                topics.append((row["heading_number"], row["heading_text"]))
    # Sort topics numerically
    topics.sort(key=lambda t: [int(x) for x in t[0].split(".") if x.isdigit()])
    return topics

def extract_all_text_blocks(doc: fitz.Document) -> List[TextBlock]:
    """Extracts all text blocks from a PDF with their locations, filtering headers/footers."""
    all_blocks = []
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        top_margin = page_height * 0.10
        bottom_margin = page_height * 0.90
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            x0, y0, x1, y1, block_text_raw, _, _ = b
            if y0 < top_margin or y1 > bottom_margin:
                continue
            text = block_text_raw.strip().replace('\n', ' ')
            if text:
                all_blocks.append(TextBlock(text=text, page=page_num, y=y0))
    return all_blocks

def find_anchor_locations(topics_from_csv: List[Tuple[str, str]], all_blocks: List[TextBlock]) -> List[TopicAnchor]:
    """Uses fuzzy matching to find the exact location of each topic from the CSV in the PDF text."""
    anchors = []
    block_texts = [block.text for block in all_blocks]
    
    for topic_num, topic_title in topics_from_csv:
        # Search for the best match for the topic title in all text blocks
        # scorer=fuzz.WRatio is good for matching sentences
        best_match = process.extractOne(topic_title, block_texts, scorer=fuzz.WRatio, score_cutoff=85)
        
        if best_match:
            match_text, score, index = best_match
            found_block = all_blocks[index]
            
            # Additional check: the topic number should also be in the matched block
            if topic_num in found_block.text:
                log(f"  [ANCHOR] Found '{topic_title}' on page {found_block.page + 1} (Score: {score:.0f})")
                anchors.append(TopicAnchor(topic_number=topic_num, title=topic_title, page=found_block.page, y=found_block.y))
            else:
                log(f"  [ANCHOR-WARN] Found title '{topic_title}' but missing number '{topic_num}'. Skipping.")
        else:
            log(f"  [ANCHOR-FAIL] Could not find a reliable location for topic: {topic_num} {topic_title}")

    # Sort the found anchors by their position in the document
    anchors.sort(key=lambda a: (a.page, a.y))
    return anchors

def assign_content_to_anchors(anchors: List[TopicAnchor], all_blocks: List[TextBlock]):
    """Assigns all text that appears between two anchors to the first anchor."""
    for i, current_anchor in enumerate(anchors):
        content_blocks = []
        # Define the start and end boundaries for this anchor's content
        start_page, start_y = current_anchor.page, current_anchor.y
        end_page = anchors[i+1].page if i + 1 < len(anchors) else float('inf')
        end_y = anchors[i+1].y if i + 1 < len(anchors) else float('inf')

        for block in all_blocks:
            # Check if the block is physically located after the current anchor...
            is_after_start = block.page > start_page or (block.page == start_page and block.y > start_y)
            # ...and before the next anchor.
            is_before_end = block.page < end_page or (block.page == end_page and block.y < end_y)

            if is_after_start and is_before_end:
                content_blocks.append(block.text)
        
        current_anchor.content = "\n".join(content_blocks)
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
        
        # 1. Load the ground-truth list of topics for this chapter
        topics_from_csv = load_topics_from_csv(CSV_PATH, subject_name, class_number, pdf_filename)
        if not topics_from_csv:
            log("  [WARNING] No topics found in CSV for this chapter. Skipping.")
            continue
            
        # 2. Extract all text blocks from the PDF
        doc = fitz.open(pdf_path)
        all_text_blocks = extract_all_text_blocks(doc)
        doc.close()
        
        # 3. Find the locations of our topics in the PDF
        anchors = find_anchor_locations(topics_from_csv, all_text_blocks)
        
        # 4. Assign all text between the found anchors
        topics_with_content = assign_content_to_anchors(anchors, all_text_blocks)
        
        # 5. Update the database
        update_count = 0
        for topic in topics_with_content:
            if topic.content:
                cursor.execute(
                    "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                    (topic.content, chapter_id, topic.topic_number)
                )
                update_count += 1
        
        conn.commit()
        log(f"  [SUCCESS] Updated {update_count} of {len(topics_from_csv)} topics for this chapter.")
    
    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")

if __name__ == '__main__':
    main()