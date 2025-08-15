import os
import re
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import psycopg2
from difflib import SequenceMatcher
import unicodedata
from dotenv import load_dotenv

# ===== Tesseract path =====
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ===== Load env vars =====
load_dotenv()

CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
PDF_DIR = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
DB_CONN = os.environ.get("SUPABASE_CONNECTION_STRING")


# ---------- OCR + Utils ----------
def pdf_to_text(pdf_path):
    """Convert PDF to text using Tesseract OCR."""
    pages = convert_from_path(pdf_path, dpi=300)
    text_pages = [pytesseract.image_to_string(pg) for pg in pages]
    return "\n".join(text_pages)


def normalize_for_match(s):
    """Remove accents, punctuation, spaces; lowercase."""
    if not s:
        return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^0-9a-zA-Z ]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()


def similar(a, b):
    """Return fuzzy similarity ratio between two strings."""
    return SequenceMatcher(None, normalize_for_match(a), normalize_for_match(b)).ratio()


# ---------- Extraction ----------
def extract_topics_and_questions(full_text, csv_topics):
    lines = full_text.split("\n")
    topics_output = []
    questions_output = []

    headings = csv_topics.to_dict("records")
    num_headings = len(headings)

    for i, h in enumerate(headings):
        heading_text = str(h["heading_text"]).strip()
        heading_number = str(h["heading_number"]).strip()

        start_idx = None
        best_score = 0
        matched_line = ""

        # Scan line-by-line with a 2-line sliding window
        for idx in range(len(lines)):
            combined_line = lines[idx]
            if idx + 1 < len(lines):
                combined_line += " " + lines[idx + 1]

            norm_line = normalize_for_match(combined_line)
            score = similar(combined_line, heading_text)

            if heading_number in norm_line or score > best_score:
                if heading_number in norm_line or score >= 0.70:
                    start_idx = idx
                    best_score = score
                    matched_line = combined_line
                    if heading_number in norm_line:  # number match → break
                        break

        # Debug info
        if start_idx is not None:
            print(f"[MATCH] {heading_number} {heading_text} -> "
                  f"Line: '{matched_line[:80]}' | Score: {best_score:.2f}")
        else:
            print(f"[MISS] {heading_number} {heading_text}")

        if start_idx is None:
            # Insert empty if no match, so DB row exists
            topics_output.append({
                "topic_number": heading_number,
                "heading_text": heading_text,
                "full_text": ""
            })
            continue

        # Determine end of topic: next heading
        end_idx = None
        if i + 1 < num_headings:
            next_heading_text = str(headings[i + 1]["heading_text"]).strip()
            next_heading_number = str(headings[i + 1]["heading_number"]).strip()
            for idx2 in range(start_idx + 1, len(lines)):
                combined_line2 = lines[idx2]
                if idx2 + 1 < len(lines):
                    combined_line2 += " " + lines[idx2 + 1]
                norm_line2 = normalize_for_match(combined_line2)
                score_next = similar(combined_line2, next_heading_text)
                if next_heading_number in norm_line2 or score_next >= 0.70:
                    end_idx = idx2
                    break
        if end_idx is None:
            end_idx = len(lines)

        topic_text = "\n".join(lines[start_idx + 1:end_idx]).strip()
        topics_output.append({
            "topic_number": heading_number,
            "heading_text": heading_text,
            "full_text": topic_text
        })

    # Extract questions only after "Exercises"
    in_exercises = False
    for line in lines:
        if not in_exercises and "exercise" in normalize_for_match(line):
            in_exercises = True
            continue
        if in_exercises:
            if re.match(r'^\(?\d+[\.\)]', line.strip()) or re.match(r'^q\d+', line.strip(), re.I):
                questions_output.append({"question_text": line.strip()})

    return topics_output, questions_output


# ---------- DB ----------
def update_database(cur, chapter_id, topics, questions):
    for t in topics:
        cur.execute("""
            UPDATE topics
            SET name = %s, full_text = %s
            WHERE chapter_id = %s AND topic_number = %s
        """, (t["heading_text"], t["full_text"], chapter_id, t["topic_number"]))

    cur.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
    for q in questions:
        cur.execute("""
            INSERT INTO question_bank (chapter_id, question_text)
            VALUES (%s, %s)
        """, (chapter_id, q["question_text"]))


# ---------- Main ----------
def main():
    if not DB_CONN:
        raise ValueError("SUPABASE_CONNECTION_STRING is missing in .env")

    # Load CSV
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, dtype=str)
        df["chapter_file"] = df["chapter_file"].str.strip()
    else:
        df = None
        print("[WARN] CSV not found — skipping topics.")

    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()
    print("[INFO] Connected to DB.")

    # Load chapters
    cur.execute("SELECT id, name FROM chapters")
    chapters_db = {row[1]: row[0] for row in cur.fetchall()}

    for root, _, files in os.walk(PDF_DIR):
        for file in sorted(files):
            if not file.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root, file)
            chapter_name = os.path.splitext(file)[0]

            if chapter_name not in chapters_db:
                print(f"[WARN] Chapter '{chapter_name}' not found in DB — skipping.")
                continue

            chapter_id = chapters_db[chapter_name]
            if df is not None:
                pdf_topics = df[df["chapter_file"].str.lower().str.rstrip(".pdf") == chapter_name.lower()]
            else:
                pdf_topics = pd.DataFrame()

            print(f"[FOUND] {pdf_path} ({len(pdf_topics)} topics from CSV)")

            full_text = pdf_to_text(pdf_path)
            topics, questions = extract_topics_and_questions(full_text, pdf_topics)

            print(f"[INFO] Extracted {len(topics)} topics and {len(questions)} questions.")

            update_database(cur, chapter_id, topics, questions)
            conn.commit()

    cur.close()
    conn.close()
    print("[DONE] All chapters processed.")


if __name__ == "__main__":
    main()
