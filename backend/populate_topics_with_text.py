import os
import re
import pandas as pd
from dataclasses import dataclass, field
from typing import List
import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv
from collections import Counter

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# ==============================================================================
# --- THIS IS THE TUNING KNOB ---
# If the script is missing headings, you can lower this number (e.g., to 7 or 6).
SCORE_THRESHOLD = 8
# ==============================================================================

def log(msg: str):
    print(msg, flush=True)

@dataclass
class TopicAnchor:
    topic_number: str; title: str; page: int; y: float
    content: str = field(default="")

def get_most_common_font_info(doc: fitz.Document) -> tuple[float, bool]:
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
    anchors = []
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    log(f"  [DEBUG] Body style identified: size ~{body_font_size}, bold: {body_is_bold}")
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

                    score_num = 5 if heading_num_pattern.match(line_text) else 0
                    score_bold = 3 if span_is_bold and not body_is_bold else 0
                    score_size = 2 if span_size > body_font_size else 0
                    score_margin = 1 if x_pos < 100 else 0
                    score = score_num + score_bold + score_size + score_margin
                    
                    if score >= 5:
                        log(f"  [SCORE] Text: '{line_text[:80]}...'")
                        log(f"    - Score: {score} (Number: {score_num}, Bold: {score_bold}, Size: {score_size}, Margin: {score_margin})")
                        if score >= SCORE_THRESHOLD:
                            log(f"    - Verdict: ACCEPTED (Score >= {SCORE_THRESHOLD})")
                        else:
                            log(f"    - Verdict: REJECTED (Score < {SCORE_THRESHOLD})")
                    
                    if score >= SCORE_THRESHOLD:
                        topic_num_match = re.match(r"^\s*([\d\.]+)", line_text)
                        if topic_num_match:
                            topic_num = topic_num_match.group(1).strip('.')
                            title = re.sub(r"^\s*[\d\.]+\s*", "", line_text).strip()
                            y_pos = b['bbox'][1]
                            anchors.append(TopicAnchor(topic_number=topic_num, title=title, page=page_num, y=y_pos))
                            
    unique_anchors = list({a.topic_number: a for a in sorted(anchors, key=lambda x: x.title, reverse=True)}.values())
    unique_anchors.sort(key=lambda a: (a.page, a.y))
    return unique_anchors

def extract_all_text_blocks(doc: fitz.Document) -> List[dict]:
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
                all_blocks.append({'text': text, 'page': page_num, 'y': y0})
    return all_blocks

def assign_content_to_anchors(anchors: List[TopicAnchor], all_blocks: List[dict]):
    for i, current_anchor in enumerate(anchors):
        content_blocks = []
        start_page, start_y = current_anchor.page, current_anchor.y
        end_page = anchors[i+1].page if i + 1 < len(anchors) else float('inf')
        end_y = anchors[i+1].y if i + 1 < len(anchors) else float('inf')
        for block in all_blocks:
            is_after_start = block['page'] > start_page or (block['page'] == start_page and block['y'] > start_y)
            is_before_end = block['page'] < end_page or (block['page'] == end_page and block['y'] < end_y)
            if is_after_start and is_before_end:
                content_blocks.append(block['text'])
        current_anchor.content = "\n".join(content_blocks).strip()
    return anchors

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        log(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    try:
        log(f"[INFO] Loading master topic list from {CSV_PATH}...")
        master_df = pd.read_csv(CSV_PATH, dtype=str)
        master_df = master_df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {CSV_PATH}")
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
        
        # --- ROBUST TOPIC FILTERING WITH PANDAS ---
        chapter_topics_df = master_df[
            (master_df['chapter_file'] == pdf_filename) &
            (master_df['subject'] == subject_name) &
            (master_df['class'] == class_number)
        ]
        
        if chapter_topics_df.empty:
            log(f"  [WARNING] No topics found in CSV for this specific chapter. Skipping.")
            continue
            
        topics_from_csv = chapter_topics_df.to_dict('records')
        
        doc = fitz.open(pdf_path)
        chapter_num_from_csv = str(topics_from_csv[0]['chapter_number'])
        log(f"  [DEBUG] Using chapter number '{chapter_num_from_csv}' for regex.")
        
        anchors = find_anchors_with_scoring(doc, chapter_num_from_csv)
        all_text_blocks = extract_all_text_blocks(doc)
        doc.close()
        
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