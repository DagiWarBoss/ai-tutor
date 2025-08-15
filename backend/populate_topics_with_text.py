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
CACHE_DIR = r"ocr_cache"  # Directory for cached OCR results

# Create cache directory if it doesn't exist
os.makedirs(CACHE_DIR, exist_ok=True)

# ---------- OCR + Cache ----------
def get_cache_path(pdf_path):
    """Return the cache file path for a given PDF file."""
    base_name = os.path.basename(pdf_path)
    cache_file = os.path.splitext(base_name)[0] + ".txt"
    return os.path.join(CACHE_DIR, cache_file)

def pdf_to_text(pdf_path):
    """Convert PDF to text using cached OCR result if available, else perform OCR and cache."""
    cache_path = get_cache_path(pdf_path)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            print(f"[CACHE HIT] Using cached OCR for '{pdf_path}'")
            return f.read()

    print(f"[OCR] Processing PDF '{pdf_path}'")
    pages = convert_from_path(pdf_path, dpi=500)  # 500 DPI for high fidelity
    text_pages = [pytesseract.image_to_string(pg) for pg in pages]
    full_text = "\n".join(text_pages)

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        print(f"[CACHE SAVE] OCR result saved to '{cache_path}'")

    return full_text

# ---------- Text Normalization and Similarity ----------
def normalize_for_match(s):
    if not s:
        return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^0-9a-zA-Z ]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

def similar(a, b):
    return SequenceMatcher(None, normalize_for_match(a), normalize_for_match(b)).ratio()

# ---------- Extraction (unchanged) ----------
def extract_topics_and_questions(full_text, csv_topics):
    lines = full_text.split("\n")
    topics_output = []
    questions_output = []

    # rest of your extraction logic unchanged...

    # ... (you can paste your existing extraction code here)

    # For brevity, do not rewrite the whole extraction code here.
    # Ensure your original extract_topics_and_questions function is included.

    pass  # Placeholder: replace with your extraction code

# ---------- Database update and main logic (unchanged) ----------
# Include your existing update_database and main() function here

# --- Example simplified main ---
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

            full_text = pdf_to_text(pdf_path)  # Uses cache

            # extract topics and questions (your function)
            topics, questions = extract_topics_and_questions(full_text, pdf_topics)

            print(f"[INFO] Extracted {len(topics)} topics and {len(questions)} questions.")

            # update your DB accordingly, with your update_database function
            update_database(cur, chapter_id, topics, questions)
            conn.commit()

    cur.close()
    conn.close()
    print("[DONE] All chapters processed.")

if __name__ == "__main__":
    main()
