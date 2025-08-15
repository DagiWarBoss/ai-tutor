import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract

# Uncomment and set this if your Tesseract executable is in a non-standard location (Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Load environment variables from .env file
load_dotenv()
DB_CONN = os.getenv("SUPABASE_CONNECTION_STRING")

if not DB_CONN:
    raise ValueError("Missing SUPABASE_CONNECTION_STRING in environment variables.")

# Configure your chapter PDFs and OCR cache locations here (use real paths on your PC)
CHAPTER_CONFIG = {
    157: {  # Chemistry Chapter 8
        "pdf": r"C:\Users\daksh\Documents\NCERT\Chemistry\Chapter_8_Chemical_Structures.pdf",
        "ocr_cache": r"ocr_cache\Chapter_8_Chemical_Structures.txt"
    },
    155: {  # Chemistry Chapter 5
        "pdf": r"C:\Users\daksh\Documents\NCERT\Chemistry\Chapter_5_Thermodynamics.pdf",
        "ocr_cache": r"ocr_cache\Chapter_5_Thermodynamics.txt"
    },
    174: {  # Mathematics Chapter 14
        "pdf": r"C:\Users\daksh\Documents\NCERT\Maths\Chapter_14_Probability.pdf",
        "ocr_cache": r"ocr_cache\Chapter_14_Probability.txt"
    },
    183: {  # Mathematics Chapter 5
        "pdf": r"C:\Users\daksh\Documents\NCERT\Maths\Chapter_5_Calculus.pdf",
        "ocr_cache": r"ocr_cache\Chapter_5_Calculus.txt"
    }
}

os.makedirs("ocr_cache", exist_ok=True)

def pdf_to_text(pdf_path, cache_path):
    """
    OCR the PDF and save output to cache_path.
    If cache exists, load from cache instead.
    """
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    print(f"[OCR] Processing {pdf_path} ...")
    pages = convert_from_path(pdf_path, dpi=400)
    text = "\n".join(pytesseract.image_to_string(img) for img in pages)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[CACHE SAVED] {cache_path}")
    return text

# List of (chapter_id, topic_number) pairs for topics to update
TOPICS_TO_EXTRACT = [
    # Fill these tuples with actual chapter IDs and topic numbers of interest
    ('157', '7.5'), ('157', '7.5.1'), ('157', '7.5.2'), ('157', '7.5.3'),
    ('158', '8.1'), ('158', '8.11'), ('158', '8.12'), ('158', '8.2'),
    ('158', '8.21'), ('158', '8.22'), ('158', '8.3'), ('158', '8.4'),
    ('158', '8.5'), ('158', '8.6'), ('158', '8.61'), ('158', '8.62'),
    ('158', '8.7'), ('158', '8.8'), ('158', '8.9'), ('158', '8.91'),
    ('158', '8.92'),
    ('155', '2.78'), ('155', '2.79'),
    ('156', '5.1'), ('156', '5.11'), ('156', '5.12'), ('156', '5.13'), ('156', '5.14'),
    ('156', '5.2'), ('156', '5.21'), ('156', '5.22'), ('156', '5.3'), ('156', '5.4'),
    ('156', '5.41'), ('156', '5.42'), ('156', '5.43'), 
    ('174', '14.1'), ('174', '14.11'), ('174', '14.12'), ('174', '14.13'),
    ('174', '14.14'), ('174', '14.15'), ('174', '14.2'), ('174', '14.21'),
    ('174', '14.22'), ('174', '14.23'), ('174', '14.24'),
    ('175', '2.1'), ('175', '2.2'), ('175', '2.3'), ('175', '2.4'),
    ('175', '2.41'), ('175', '2.42'),
    ('176', '8.1'), ('176', '8.2'), ('176', '8.3'), ('176', '8.4'),
    ('183', '5.1'), ('183', '5.2'), ('183', '5.21'), ('183', '5.3'),
    ('183', '5.31'), ('183', '5.32'), ('183', '5.33'), ('183', '5.4'),
    ('183', '5.5'), ('183', '5.6'),
    # Add or adjust as needed
]

def extract_topic_text(content, topic_number):
    """
    Extract the text for a given topic_number in content.
    Matches from topic header till next topic header or document end.
    """
    pattern = re.compile(
        rf'^{re.escape(topic_number)}\s.*?(?=^\d+(\.\d+)*\s|\Z)', 
        re.DOTALL | re.MULTILINE)
    match = pattern.search(content)
    return match.group().strip() if match else ""

def main():
    # OCR or load text for each chapter in scope
    chapter_texts = {}
    for chapter_id, paths in CHAPTER_CONFIG.items():
        pdf_path = paths["pdf"]
        cache_path = paths["ocr_cache"]
        if not os.path.exists(pdf_path):
            print(f"PDF not found: {pdf_path}")
            continue
        chapter_texts[int(chapter_id)] = pdf_to_text(pdf_path, cache_path)

    # Connect to Postgres DB
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    # Extract topic text and update database
    for chapter_id_str, topic_number in TOPICS_TO_EXTRACT:
        chapter_id = int(chapter_id_str)
        if chapter_id not in chapter_texts:
            print(f"No text available for chapter {chapter_id}, skipping topic {topic_number}")
            continue
        content = chapter_texts[chapter_id]
        topic_text = extract_topic_text(content, topic_number)
        if not topic_text:
            print(f"No text extracted for topic {topic_number} in chapter {chapter_id}")
            continue
        try:
            cur.execute("""
                UPDATE public.topics
                SET full_text = %s
                WHERE chapter_id = %s AND topic_number = %s
            """, (topic_text, chapter_id, topic_number))
            print(f"Updated topic {topic_number} in chapter {chapter_id}")
        except Exception as e:
            print(f"Failed to update topic {topic_number} in chapter {chapter_id}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("All done.")

if __name__ == "__main__":
    main()
