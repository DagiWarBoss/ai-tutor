import os
import re
import csv
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv
from collections import Counter

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

def get_most_common_font_info(doc: fitz.Document) -> Tuple[float, bool]:
    """Finds the font size and bold status of the main body text."""
    font_counts = Counter()
    for page_num, page in enumerate(doc):
        if page_num > 5: break
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        key = (round(s["size"]), "bold" in s["font"].lower())
                        font_counts[key] += len(s.get("text", ""))
    if not font_counts: return (10.0, False)
    return font_counts.most_common(1)[0][0]

def find_anchors_with_scoring(doc: fitz.Document, chapter_number: str) -> List[TopicAnchor]:
    """
    --- NEW HEURISTIC SCORING LOGIC ---
    Finds headings by scoring each line based on multiple text and style features.
    """
    anchors = []
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    heading_num_pattern = re.compile(rf"^\s*({chapter_number}(?:\.\d+){0,5})")

    for page_num, page in enumerate(doc):
        styled_blocks = page.get_text("dict")["blocks"]
        for b in styled_blocks:
            if "lines" in b:
                for l in b["lines"]:
                    if not l["spans"]: continue
                    
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    first_span = l["spans"][0]
                    span_size = round(first_span["size"])
                    span_is_bold = "bold" in first_span["font"].lower()
                    x_pos = l["bbox"][0]

                    # --- Scoring System ---
                    score = 0
                    match = heading_num_pattern.match(line_text)
                    if match:
                        score += 5
                    if span_is_bold and not body_is_bold:
                        score += 3
                    if span_size > body_font_size:
                        score += 2
                    if x_pos < 100: # Is it near the left margin?
                        score += 1
                    
                    # --- Threshold ---
                    if score >= 8: # A high score means it's very likely a heading
                        topic_num_match = re.match(r"^\s*([\d\.]+)", line_text)
                        if topic_num_match:
                            topic_num = topic_num_match.group(1).strip('.')
                            title = re.sub(r"^\s*[\d\.]+\s*", "", line_text).strip()
                            y_pos = b['bbox'][1]
                            
                            log(f"  [ANCHOR] Found '{line_text}' on page {page_num + 1} (Score: {score})")
                            anchors.append(TopicAnchor(topic_number=topic_num, title=title, page=page_num, y=y_pos))
                            
    # Deduplicate and sort
    unique_anchors = list({a.topic_number: a for a in sorted(anchors, key=lambda x: x.title, reverse=True)}.values())
    unique_anchors.sort(key=lambda a: (a.page, a.y))
    return unique_anchors


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
        
        topics_from_csv = load_topics_from_csv(CSV_PATH, pdf_filename)
        if not topics_from_csv:
            log(f"  [WARNING] No topics found in CSV for '{pdf_filename}'. Skipping.")
            continue
            
        doc = fitz.open(pdf_path)
        chapter_num_from_csv = topics_from_csv[0][0].split('.')[0]
        
        # 1. Find all possible headings using the scoring system
        anchors = find_anchors_with_scoring(doc, chapter_num_from_csv)
        
        # 2. Extract all text blocks from the PDF
        all_text_blocks = extract_all_text_blocks(doc)
        doc.close()
        
        # 3. Assign content between the found anchors
        topics_with_content = assign_content_to_anchors(anchors, all_text_blocks)
        
        # 4. Update the database
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