import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv
import psycopg2
from collections import Counter

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# ==============================================================================
# --- Hardcoded chapter numbers. REQUIRED for topic heading detection. ---
CHAPTER_NUMBER_FALLBACK_MAP = {
    # [as before; full dictionary of chapters ...]
    "Some Basic Concepts Of Chemistry.pdf": "1",
    # ... (rest omitted for brevity; include your full dict here)
}
# ==============================================================================

def get_most_common_font_info(doc):
    font_counts = Counter()
    for page_num, page in enumerate(doc):
        if page_num > 10:
            break  # For speed, look at first few pages only
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        key = (round(s["size"]), "bold" in s["font"].lower())
                        font_counts[key] += 1
    if not font_counts:
        print("[DEBUG] No font info found, using default")
        return (10.0, False)
    print(f"[DEBUG] Most common font: {font_counts.most_common(1)[0][0]}")
    return font_counts.most_common(1)[0][0]

def extract_text_and_headings_with_location(doc, chapter_number):
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    print(f"[DEBUG] Detect body font size={body_font_size}, bold={body_is_bold}")
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+([A-Za-z].*)$")
    headings, all_text_blocks = [], []

    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            block_text, y_pos = b[4].strip().replace('\n', ' '), b[1]
            if block_text:
                all_text_blocks.append({'text': block_text, 'page': page_num, 'y': y_pos})

        styled_blocks = page.get_text("dict", flags=fitz.TEXT_INHIBIT_SPACES)["blocks"]
        for b in styled_blocks:
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    if pat.match(line_text):
                        first_span = l["spans"][0]
                        span_size = round(first_span["size"])
                        span_is_bold = "bold" in first_span["font"].lower()
                        is_heading = (span_size > body_font_size) or (span_is_bold and not body_is_bold)
                        if is_heading:
                            y_pos = b['bbox'][1]
                            headings.append({'text': line_text, 'page': page_num, 'y': y_pos})
                            print(f"[DEBUG] Heading found: '{line_text}' on page {page_num}, y={y_pos}")

    # Deduplicate headings (some may repeat on page footers/headers)
    unique_headings = list({h['text']: h for h in headings}.values())
    print(f"[DEBUG] Total headings found: {len(unique_headings)} [...{[h['text'] for h in unique_headings]}]")
    print(f"[DEBUG] Total text blocks extracted: {len(all_text_blocks)}")
    return unique_headings, all_text_blocks

def map_text_to_headings(headings, all_text_blocks):
    topic_content = {}
    sorted_headings = sorted(headings, key=lambda h: (h['page'], h['y']))

    for i, heading in enumerate(sorted_headings):
        content = []
        start_page, start_y = heading['page'], heading['y']
        end_page = sorted_headings[i+1]['page'] if i + 1 < len(sorted_headings) else float('inf')
        end_y = sorted_headings[i+1]['y'] if i + 1 < len(sorted_headings) else float('inf')

        for block in all_text_blocks:
            is_after_start = block['page'] > start_page or (block['page'] == start_page and block['y'] > start_y)
            is_before_end = block['page'] < end_page or (block['page'] == end_page and block['y'] < end_y)
            if is_after_start and is_before_end:
                is_a_heading = any(h['text'] == block['text'] for h in sorted_headings)
                if not is_a_heading:
                    content.append(block['text'])

        topic_content[heading['text']] = "\n".join(content)
        print(f"[DEBUG] Mapped topic '{heading['text']}' — content length: {len(topic_content[heading['text']])}")

    return topic_content

def main():
    print(f"[INFO] Connecting to Supabase/Postgres...")
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
    chapters_to_process = cursor.fetchall()
    print(f"[INFO] Chapters to process: {len(chapters_to_process)}")

    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)

        print(f"\n[INFO] Processing: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found at path, skipping: '{pdf_path}'")
            continue

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"  [ERROR] Could not open PDF '{pdf_path}': {e}")
            continue

        # --- Use only the hardcoded map for chapter numbers
        chapter_num = CHAPTER_NUMBER_FALLBACK_MAP.get(pdf_filename)

        if chapter_num:
            print(f"  [INFO] Using Chapter Number from map: {chapter_num}")
            headings, all_text = extract_text_and_headings_with_location(doc, chapter_num)
            topic_content_map = map_text_to_headings(headings, all_text)

            print(f"  - Found {len(topic_content_map)} topics with text to update.")
            for heading_full, content in topic_content_map.items():
                match = re.match(r"^\s*([\d\.]+)\s*[\s\.:;\-–]+(.*)$", heading_full)
                if match and content:
                    topic_num = match.group(1)
                    print(f"  [DEBUG] Updating DB for chapter_id={chapter_id}, topic_num={topic_num}, content_length={len(content)}")
                    cursor.execute(
                        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (content, chapter_id, topic_num)
                    )
                    print(f"    [DEBUG] Rows affected: {cursor.rowcount}")
                else:
                    print(f"    [WARN] Heading match failed or empty content for: '{heading_full}'")
        else:
            print(f"  [ERROR] '{pdf_filename}' not found in chapter map. Add it to CHAPTER_NUMBER_FALLBACK_MAP.")
        doc.close()

    conn.commit()
    cursor.close()
    conn.close()
    print("\n[SUCCESS] All topics have been updated with their full text content.")

if __name__ == '__main__':
    main()
