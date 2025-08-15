import os
import re
import psycopg2
from dotenv import load_dotenv

from pdf2image import convert_from_path
import pytesseract

# Setup Tesseract path if required (Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 1. Load environment variables
load_dotenv()
DB_CONN = os.getenv("SUPABASE_CONNECTION_STRING")
if not DB_CONN:
    raise ValueError("Missing SUPABASE_CONNECTION_STRING in environment variables.")

# 2. Specify your PDF and OCR cache details
CHAPTER_CONFIG = {
    157: {
        "pdf": r"path\to\Chemistry_Chapter_8.pdf",
        "ocr_cache": r"ocr_cache\Chemistry_Chapter_8.txt"
    },
    155: {
        "pdf": r"path\to\Chemistry_Chapter_5.pdf",
        "ocr_cache": r"ocr_cache\Chemistry_Chapter_5.txt"
    },
    174: {
        "pdf": r"path\to\Mathematics_Chapter_14.pdf",
        "ocr_cache": r"ocr_cache\Mathematics_Chapter_14.txt"
    },
    183: {
        "pdf": r"path\to\Mathematics_Chapter_5.pdf",
        "ocr_cache": r"ocr_cache\Mathematics_Chapter_5.txt"
    }
}

os.makedirs("ocr_cache", exist_ok=True)

def pdf_to_text(pdf_path, cache_path):
    """
    Perform OCR on a PDF, with caching.
    Returns the full extracted text.
    """
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    print(f"[OCR] Processing {pdf_path} ...")
    pages = convert_from_path(pdf_path, dpi=400)
    text = "\n".join([pytesseract.image_to_string(img) for img in pages])
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[CACHE SAVED] {cache_path}")
    return text

# 3. List topics you want (as tuples of chapter_id and topic_number)
TOPICS_TO_EXTRACT = [
    ('157', '7.5'), ('157', '7.5.1'), ('157', '7.5.2'), ('157', '7.5.3'),
    # ... add all topic tuples as needed ...
    ('183', '5.1'), ('183', '5.2'), ('183', '5.3'), # etc
]

def extract_topic_text_from_content(content, topic_number):
    # Matches lines starting with the topic_number, until the next topic header or EOF.
    pattern = re.compile(
        rf'^\s*{re.escape(topic_number)}\s.*?(?=^\s*\d+(\.\d+)*\s|\Z)',
        re.DOTALL | re.MULTILINE)
    match = pattern.search(content)
    return match.group().strip() if match else ""

def main():
    # 1. OCR only the requested chapters
    chap_contents = {}
    for chapter_id, paths in CHAPTER_CONFIG.items():
        pdf = paths["pdf"]
        cache = paths["ocr_cache"]
        if not os.path.exists(cache):
            if not os.path.exists(pdf):
                print(f"PDF not found for chapter {chapter_id}: {pdf}")
                continue
            chap_contents[chapter_id] = pdf_to_text(pdf, cache)
        else:
            with open(cache, "r", encoding="utf-8") as f:
                chap_contents[chapter_id] = f.read()

    # 2. DB connection
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    # 3. Extract for ONLY listed topics and update DB
    for chapter_id, topic_number in TOPICS_TO_EXTRACT:
        chap_id_int = int(chapter_id)
        if chap_id_int not in chap_contents:
            print(f"No OCR text for chapter {chapter_id}, skipping topic {topic_number}")
            continue
        content = chap_contents[chap_id_int]
        text = extract_topic_text_from_content(content, topic_number)
        if not text:
            print(f"No text found for topic {topic_number} in chapter {chapter_id}")
            continue
        try:
            cur.execute("""
                UPDATE public.topics
                SET full_text = %s
                WHERE chapter_id = %s AND topic_number = %s
            """, (text, chap_id_int, topic_number))
            print(f"Updated topic {topic_number} in chapter {chapter_id}")
        except Exception as e:
            print(f"Error updating {topic_number} in {chapter_id}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
