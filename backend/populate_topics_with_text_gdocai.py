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
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ===== Load env vars =====
load_dotenv()

CSV_PATH = r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\final_verified_topics.csv"
PDF_DIR = r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise"
DB_CONN = os.environ.get("SUPABASE_CONNECTION_STRING")

# ---------- OCR + Utils ----------
def pdf_to_text(pdf_path):
    """Convert PDF to text using Tesseract OCR with 500 DPI."""
    pages = convert_from_path(pdf_path, dpi=500)  # <--- 500 DPI for high fidelity!
    text_pages = [pytesseract.image_to_string(pg) for pg in pages]
    return "\n".join(text_pages)

def normalize_for_match(s):
    if not s: return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^0-9a-zA-Z ]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

def similar(a, b):
    return SequenceMatcher(None, normalize_for_match(a), normalize_for_match(b)).ratio()

# ---------- Extraction ----------
def extract_topics_and_questions(full_text, csv_topics):
    lines = full_text.split("\n")
    topics_output = []
    questions_output = []

    headings = csv_topics.to_dict("records")
    # --- Fuzzy multi-line merge match for headings ---
    def fuzzy_find_heading(lines, heading, heading_number, max_merge=4, threshold=0.70):
        best_idx, best_score, best_line = -1, 0, ""
        for i in range(len(lines)):
            for merge in range(1, max_merge+1):
                chunk = " ".join([lines[j].strip() for j in range(i, min(i+merge, len(lines)))])
                score = similar(chunk, heading)
                if heading_number in normalize_for_match(chunk) or score > best_score:
                    if heading_number in normalize_for_match(chunk) or score >= threshold:
                        if score > best_score or heading_number in normalize_for_match(chunk):
                            best_idx, best_score, best_line = i, score, chunk
                            if heading_number in normalize_for_match(chunk):
                                return best_idx, best_score, best_line
        return best_idx, best_score, best_line

    indices = []
    for h in headings:
        heading_number = str(h["heading_number"]).strip()
        heading_text = str(h["heading_text"]).strip()
        idx, score, matched = fuzzy_find_heading(lines, heading_text, heading_number)
        if idx != -1:
            print(f"[MATCH] {heading_number} {heading_text} -> '{matched[:60]}' | Score: {score:.2f}")
        else:
            print(f"[MISS] {heading_number} {heading_text}")
        indices.append((idx, heading_number, heading_text))
    indices = [i for i in indices if i[0] != -1]
    indices = sorted(indices, key=lambda x: x)

    for i, (start_idx, heading_number, heading_text) in enumerate(indices):
        end_idx = indices[i+1] if i+1 < len(indices) else len(lines)
        topic_text = "\n".join(lines[start_idx+1:end_idx]).strip()
        topics_output.append({
            "topic_number": heading_number,
            "heading_text": heading_text,
            "full_text": topic_text
        })

    # --- Full exercise question extraction ---
    in_exercise = False
    exercise_headers = ['exercise', 'exercises', 'practice', 'questions']
    question_ptrn = re.compile(r'^(\(?\d{1,3}[\.|\)]|\(?[a-zA-Z][\)\.]|Q\s?\d{1,3}[\. :]?)')
    buffer = []
    for line in lines:
        normline = normalize_for_match(line)
        # locate Exercises start
        if not in_exercise and any(eh in normline for eh in exercise_headers):
            in_exercise = True
            continue
        if in_exercise:
            if question_ptrn.match(line.strip()):
                if buffer:
                    full_q = " ".join(buffer).strip()
                    if len(full_q) > 2:
                        questions_output.append({"question_text": full_q})
                    buffer = []
                buffer = [line]
            elif buffer:
                buffer.append(line)
    if buffer:
        full_q = " ".join(buffer).strip()
        if len(full_q) > 2:
            questions_output.append({"question_text": full_q})

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

    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, dtype=str)
        df["chapter_file"] = df["chapter_file"].str.strip()
    else:
        df = None
        print("[WARN] CSV not found — skipping topics.")

    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()
    print("[INFO] Connected to DB.")

    cur.execute("SELECT id, name FROM chapters")
    chapters_db = {row[1]: row for row in cur.fetchall()}

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
