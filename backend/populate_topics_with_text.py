import os
import re
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import psycopg2
from difflib import SequenceMatcher
import unicodedata
from dotenv import load_dotenv

# ==== Tesseract executable path ====
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ==== Load environment variables ====
load_dotenv()

CSV_PATH = r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\final_verified_topics.csv"
PDF_DIR = r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise"
DB_CONN = os.environ.get("SUPABASE_CONNECTION_STRING")
CACHE_DIR = "ocr_cache"  # Directory for caching OCR text files

# Create cache directory if it does not exist
os.makedirs(CACHE_DIR, exist_ok=True)


# ===== OCR with caching =====
def get_cache_path(pdf_path):
    base_name = os.path.basename(pdf_path)
    cache_file = os.path.splitext(base_name)[0] + ".txt"
    return os.path.join(CACHE_DIR, cache_file)


def pdf_to_text(pdf_path):
    """
    Converts a PDF to text by OCR. Uses cached result if available.
    """
    cache_path = get_cache_path(pdf_path)
    print(f"Looking for OCR cache at: {os.path.abspath(cache_path)}")
    if os.path.exists(cache_path):
        print("Cache found! Using cached OCR text.")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    print(f"Cache not found. Performing OCR on '{pdf_path}'")
    pages = convert_from_path(pdf_path, dpi=500)
    text_pages = [pytesseract.image_to_string(pg) for pg in pages]
    full_text = "\n".join(text_pages)

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        print(f"Saved OCR text cache at '{cache_path}'")

    return full_text


# ==== Utility functions for text processing ====
def normalize_for_match(s):
    if not s:
        return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^0-9a-zA-Z ]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()


def similar(a, b):
    return SequenceMatcher(None, normalize_for_match(a), normalize_for_match(b)).ratio()


# ==== Extraction functions ====
def extract_topics_and_questions(full_text, csv_topics_df):
    lines = full_text.split("\n")
    topics_output = []
    questions_output = []

    # Normalize all topics from CSV to speed matching
    csv_topics = []
    csv_topics_set = set()
    if csv_topics_df is not None and not csv_topics_df.empty:
        for idx, row in csv_topics_df.iterrows():
            title = row.get("topic_title") or ""
            topic_norm = normalize_for_match(title)
            csv_topics.append((topic_norm, row.to_dict()))
            csv_topics_set.add(topic_norm)
    else:
        csv_topics = []
        csv_topics_set = set()

    current_topic = None

    for i, line in enumerate(lines):
        line_strip = line.strip()
        # Skip if empty or too short
        if len(line_strip) < 3:
            continue

        # Try to detect a topic line - heuristic: lines that match any CSV topic well enough
        norm_line = normalize_for_match(line_strip)
        found_topic = None
        max_sim = 0.0
        for t_norm, t_row in csv_topics:
            sim = similar(norm_line, t_norm)
            if sim > 0.6 and sim > max_sim:
                max_sim = sim
                found_topic = t_row
        if found_topic:
            # Found a new topic
            if current_topic:
                topics_output.append(current_topic)
            current_topic = {
                "title": found_topic.get("topic_title"),
                "serial_no": found_topic.get("serial_no"),
                "page": found_topic.get("page_no"),
                "difficulty": found_topic.get("difficulty"),
                "topic_text": "",  # Will fill below
            }
            # Capture topic text - possibly the line(s) starting from this current line
            topic_text_lines = []
            for j in range(i+1, len(lines)):
                nxt = lines[j].strip()
                if len(nxt) == 0:
                    continue
                # Check if next line resembles a topic header or question
                nxt_norm = normalize_for_match(nxt)
                # Stop if next line looks like a topic
                if nxt_norm in csv_topics_set:
                    break
                # Stop if line looks like a question: contains '?'
                if "?" in nxt:
                    break
                topic_text_lines.append(nxt)
            current_topic["topic_text"] = " ".join(topic_text_lines).strip()
            continue

        # If line looks like a question (ends with '?'), try to capture question text
        if line_strip.endswith("?") or "?" in line_strip:
            question_text = line_strip
            questions_output.append({
                "question": question_text,
                "topic_title": current_topic["title"] if current_topic else None,
                "serial_no": current_topic["serial_no"] if current_topic else None,
                "page": current_topic["page"] if current_topic else None,
            })

    # Append last topic if any
    if current_topic:
        topics_output.append(current_topic)

    return topics_output, questions_output


# ==== Database update helper ====
def update_database(cur, chapter_id, topics_list, questions_list):
    """
    Update the database with extracted topics and questions for given chapter_id.
    Insert topics and linked questions.
    """
    # Insert topics
    for topic in topics_list:
        try:
            cur.execute("""
                INSERT INTO topics (chapter_id, title, serial_no, page, topic_text)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chapter_id, title) DO UPDATE SET
                    serial_no = EXCLUDED.serial_no,
                    page = EXCLUDED.page,
                    topic_text = EXCLUDED.topic_text
                RETURNING id
            """, (chapter_id,
                  topic.get("title"),
                  int(topic.get("serial_no") or 0),
                  int(topic.get("page") or 0),
                  topic.get("topic_text")))
            topic_id = cur.fetchone()[0]

            # Insert related questions for this topic
            for question in questions_list:
                if question.get("topic_title") == topic.get("title") and question.get("serial_no") == topic.get("serial_no"):
                    cur.execute("""
                        INSERT INTO questions (topic_id, question_text)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (topic_id, question.get("question")))
        except Exception as e:
            print(f"Error inserting topic '{topic.get('title')}': {e}")
            raise


# ==== Main processing function ====
def main():
    if not DB_CONN:
        raise ValueError("SUPABASE_CONNECTION_STRING is missing in .env")

    # Load CSV for topics data
    if os.path.exists(CSV_PATH):
        df_topics = pd.read_csv(CSV_PATH, dtype=str)
        df_topics["chapter_file"] = df_topics["chapter_file"].str.strip()
    else:
        df_topics = None
        print("[WARN] CSV file not found; topic matching may be less accurate.")

    # Connect to DB
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()
    print("[INFO] Database connected.")

    # Fetch chapters from database to map filenames to chapter ids
    cur.execute("SELECT id, name FROM chapters")
    db_chapters = {row[1]: row[0] for row in cur.fetchall()}

    # Walk through PDF directory and process them
    for root, _, files in os.walk(PDF_DIR):
        for file_name in sorted(files):
            if not file_name.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root, file_name)
            chapter_name = os.path.splitext(file_name)[0]

            if chapter_name not in db_chapters:
                print(f"[WARN] Chapter '{chapter_name}' not in DB, skipping {pdf_path}")
                continue

            chapter_id = db_chapters[chapter_name]

            # Filter CSV topics for this chapter
            if df_topics is not None:
                csv_filtered = df_topics[df_topics["chapter_file"].str.lower() == file_name.lower()]
            else:
                csv_filtered = pd.DataFrame()

            print(f"[PROCESS] OCR & extraction for '{pdf_path}'")

            # OCR to text with caching
            full_text = pdf_to_text(pdf_path)

            # Extract topics and questions
            topics, questions = extract_topics_and_questions(full_text, csv_filtered)

            print(f"[EXTRACTED] {len(topics)} topics and {len(questions)} questions from '{chapter_name}'")

            # Update database for each chapter - commit after each chapter to avoid long transactions
            try:
                update_database(cur, chapter_id, topics, questions)
                conn.commit()
            except Exception as e:
                print(f"[ERROR] Database update failed for '{chapter_name}': {e}")
                conn.rollback()

    cur.close()
    conn.close()
    print("[DONE] Processing completed.")


if __name__ == "__main__":
    main()
