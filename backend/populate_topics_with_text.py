import os
import re
import fitz  # PyMuPDF
import pandas as pd
from difflib import SequenceMatcher
import psycopg2
from dotenv import load_dotenv

# -------------------- CONFIG --------------------
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")  # Full Postgres connection string
# ------------------------------------------------

def log(msg): print(msg, flush=True)

def similar(a, b): return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_headings(doc, chapter_number, topics, topic_colname, title_colname):
    anchors = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            text = b[4].strip()
            for topic in topics:
                tnum = topic[topic_colname]
                ttitle = topic[title_colname]
                # Try matching: line starts with topic number, then fuzzy title match
                if text.startswith(tnum):
                    heading_title = re.sub(rf'^{re.escape(tnum)}[\s:.-]*', '', text)
                    if similar(ttitle, heading_title) > 0.6:
                        anchors.append({
                            'topic_number': tnum,
                            'title': ttitle,
                            'page': page_num,
                            'y': b[1]
                        })
    anchors.sort(key=lambda x: (x['page'], x['y']))
    return anchors

def extract_topic_contents(doc, anchors):
    all_blocks = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            text = b[4].strip()
            y0 = b[1]
            if text:
                all_blocks.append({'text': text, 'page': page_num, 'y': y0})
    for i, anchor in enumerate(anchors):
        start_page, start_y = anchor['page'], anchor['y']
        end_page = anchors[i + 1]['page'] if i + 1 < len(anchors) else float('inf')
        end_y = anchors[i + 1]['y'] if i + 1 < len(anchors) else float('inf')
        topic_blocks = []
        for block in all_blocks:
            is_after = (block['page'] > start_page) or (block['page'] == start_page and block['y'] > start_y)
            is_before = (block['page'] < end_page) or (block['page'] == end_page and block['y'] < end_y)
            if is_after and is_before:
                topic_blocks.append(block['text'])
        anchor['content'] = "\n".join(topic_blocks)
    return anchors

def update_topic_in_db(cursor, chapter_id, topic_number, content):
    cursor.execute(
        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
        (content, chapter_id, topic_number)
    )

def main():
    # ---------- Connect to DB ----------
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        log(f"[ERROR] Could not connect to DB: {e}")
        return

    # ---------- Load CSV ----------
    try:
        master_df = pd.read_csv(CSV_PATH, dtype=str)
        master_df = master_df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except Exception as e:
        log(f"[ERROR] Could not read {CSV_PATH}: {e}")
        return

    log(f"CSV Columns: {master_df.columns.tolist()}")
    # Automatically detect topic number and title column names
    topic_colname = None
    title_colname = None
    # Suggest common alternatives if not found
    for col in master_df.columns:
        if col.lower().replace(" ", "_") in ("topic_number", "number", "topic_no"):
            topic_colname = col
        if col.lower().replace(" ", "_") in ("name", "title", "topic_title"):
            title_colname = col
    if not topic_colname or not title_colname:
        raise Exception("Topic number and/or topic title column not found. Please check CSV.")

    # ---------- Load DB chapters and subjects ----------
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
    chapters_in_db = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects_map = {str(sub_id): sub_name for sub_id, sub_name in cursor.fetchall()}

    for chapter_id, chapter_name, class_number, subject_id in chapters_in_db:
        subject_name = subjects_map.get(str(subject_id))
        if not subject_name: continue

        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
        log(f"\n--- Processing: {pdf_filename} ---")
        if not os.path.exists(pdf_path):
            log(f"  [WARNING] PDF not found.")
            continue

        chapter_topics_df = master_df[
            (master_df['chapter_file'] == pdf_filename) &
            (master_df['subject'] == subject_name) &
            (master_df['class'] == class_number)
        ]
        if chapter_topics_df.empty:
            log(f"  [WARNING] No topics for chapter in CSV. Skipping.")
            continue

        topics_from_csv = chapter_topics_df.to_dict('records')
        doc = fitz.open(pdf_path)
        chap_num = str(chapter_topics_df.iloc[0]['chapter_number'])
        anchors = find_headings(doc, chap_num, topics_from_csv, topic_colname, title_colname)
        if not anchors:
            log(f"[MISS] No anchors found for {pdf_filename}")
            doc.close()
            continue
        log(f"  [INFO] Found {len(anchors)} anchors.")

        topics_with_content = extract_topic_contents(doc, anchors)
        doc.close()
        update_count = 0
        for topic in topics_with_content:
            if topic['content']:
                update_topic_in_db(cursor, chapter_id, topic['topic_number'], topic['content'])
                update_count += 1

        if update_count > 0:
            conn.commit()
        log(f"  [SUCCESS] Updated {update_count} topics for this chapter.")

    cursor.close()
    conn.close()
    log("\n[COMPLETE] Script finished.")

if __name__ == "__main__":
    main()
