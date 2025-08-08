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

def get_most_common_font_info(doc):
    """Finds the font size and bold status of the main body text."""
    font_counts = Counter()
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        key = (round(s["size"]), "bold" in s["font"].lower())
                        font_counts[key] += 1
    if not font_counts: return (10.0, False)
    return font_counts.most_common(1)[0][0]

def find_chapter_number(doc):
    """Scans the first 3 pages of a PDF to find the chapter number automatically."""
    for page_num in range(min(3, doc.page_count)):
        page_text = doc[page_num].get_text()
        chapter_match = re.search(r"CHAPTER\s+(\d{1,2})", page_text, re.IGNORECASE)
        if chapter_match: return chapter_match.group(1)
        unit_match = re.search(r"UNIT\s+(\d+)", page_text, re.IGNORECASE)
        if unit_match: return unit_match.group(1)
        code_match = re.search(r"[A-Z]{2}(\d{2})", page_text)
        if code_match: return str(int(code_match.group(1)))
    return None

def extract_text_and_headings_with_location(doc, chapter_number):
    """Extracts all text blocks and identifies headings by style, keeping their location."""
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    print(f"  [DEBUG] Body style: size ~{body_font_size}, bold: {body_is_bold}")
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")
    headings, all_text_blocks = [], []

    for page_num, page in enumerate(doc):
        # Get all text blocks with their positions
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            block_text, y_pos = b[4].strip(), b[1]
            if block_text:
                all_text_blocks.append({'text': block_text, 'page': page_num, 'y': y_pos})
        
        # Analyze the styled text to identify which blocks are headings
        styled_blocks = page.get_text("dict", flags=fitz.TEXT_INHIBIT_SPACES)["blocks"]
        for b in styled_blocks:
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    match = pat.match(line_text)
                    
                    # --- START OF DEBUG BLOCK ---
                    if match:
                        first_span = l["spans"][0]
                        span_size = round(first_span["size"])
                        span_font = first_span["font"]
                        span_is_bold = "bold" in span_font.lower()
                        
                        is_heading_style = (span_size > body_font_size) or (span_is_bold and not body_is_bold)
                        
                        print(f"\n[DEBUG] Regex Matched Line: '{line_text}'")
                        print(f"  - Font: {span_font}, Size: {span_size}")
                        print(f"  - Is Bold: {span_is_bold}")
                        
                        if is_heading_style:
                            print("  - VERDICT: ACCEPTED as a heading.")
                            y_pos = b['bbox'][1]
                            headings.append({'text': line_text, 'page': page_num, 'y': y_pos})
                        else:
                            print("  - VERDICT: REJECTED due to font style/size not matching heading criteria.")
                    # --- END OF DEBUG BLOCK ---
                            
    unique_headings = list({h['text']: h for h in headings}.values())
    return unique_headings, all_text_blocks

def map_text_to_headings(headings, all_text_blocks):
    """Assigns text blocks to the heading they fall under."""
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
    return topic_content

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
    chapters_to_process = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
        
        print(f"\nProcessing: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found. Skipping.")
            continue
            
        doc = fitz.open(pdf_path)
        
        chapter_num = find_chapter_number(doc)
        if not chapter_num:
            print("  [INFO] Auto-detection failed. Checking fallback map...")
            chapter_num = CHAPTER_NUMBER_FALLBACK_MAP.get(pdf_filename)

        if chapter_num:
            print(f"  [INFO] Using Chapter Number: {chapter_num}")
            headings, all_text = extract_text_and_headings_with_location(doc, chapter_num)
            topic_content_map = map_text_to_headings(headings, all_text)
            
            print(f"  - Found {len(topic_content_map)} topics with text to update.")

            for heading_full, content in topic_content_map.items():
                match = re.match(r"^\s*([\d\.]+)\s*[\s\.:;\-–]+(.*)$", heading_full)
                if match and content:
                    topic_num = match.group(1)
                    cursor.execute(
                        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (content, chapter_id, topic_num)
                    )
        else:
            print(f"  [ERROR] Could not determine chapter number for '{pdf_filename}'. Skipping.")
        
        doc.close()
    
    conn.commit()
    cursor.close()
    conn.close()
    print("\n[SUCCESS] All topics have been updated with their full text content.")

if __name__ == '__main__':
    main()