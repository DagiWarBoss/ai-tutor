import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract

# Uncomment and set this if your Tesseract executable is in a custom location (Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Load environment variables
load_dotenv()
DB_CONN = os.getenv("SUPABASE_CONNECTION_STRING")

if not DB_CONN:
    raise ValueError("Missing SUPABASE_CONNECTION_STRING in environment variables.")

# Map chapters to actual PDF paths and cache files
CHAPTER_CONFIG = {
    157: {  # Chemistry 11 - Chapter "Chemical Bonding and Molecular Structure"
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\NCERT_PCM\ChapterWise\Chemistry\Class 11\Chemical Bonding and Molecular Structure.pdf",
        "ocr_cache": r"ocr_cache\Chemical_Bonding_and_Molecular_Structure_11.txt"
    },
    155: {  # Chemistry 12 - replace with actual filename
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\NCERT_PCM\ChapterWise\Chemistry\Class 12\Thermodynamics.pdf",
        "ocr_cache": r"ocr_cache\Thermodynamics_12.txt"
    },
    174: {  # Maths 12 - example filename, adjust as per actual
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\NCERT_PCM\ChapterWise\Mathematics\Class 12\Probability.pdf",
        "ocr_cache": r"ocr_cache\Probability_12.txt"
    },
    183: {  # Maths 12 - example filename, adjust as per actual
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\NCERT_PCM\ChapterWise\Mathematics\Class 12\Calculus.pdf",
        "ocr_cache": r"ocr_cache\Calculus_12.txt"
    }
}

os.makedirs("ocr_cache", exist_ok=True)

def pdf_to_text(pdf_path, cache_path):
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

# List of (chapter_id, topic_number) pairs to extract & update
TOPICS_TO_EXTRACT = [
    # Add your topics here as ("chapter_id", "topic_number")
    ('157', '7.5'), ('157', '7.5.1'), ('157', '7.5.2'),  # etc.
    ('155', '2.1'), ('155', '2.2'),  # add actual topics
    ('174', '14.1'), ('174', '14.2'), 
    ('183', '5.1'), ('183', '5.2'),
    # Extend as needed...
]

def extract_topic_text(content, topic_number):
    pattern = re.compile(
        rf'^({re.escape(topic_number)})\b.*?(?=^\d+(\.\d+)*\b|\Z)', re.MULTILINE | re.DOTALL)
    match = pattern.search(content)
    return match.group().strip() if match else ""

def main():
    chap_texts = {}
    for chap_id, paths in CHAPTER_CONFIG.items():
        pdf_path = paths["pdf"]
        cache_path = paths["ocr_cache"]
        if not os.path.exists(pdf_path):
            print(f"PDF not found: {pdf_path}")
            continue
        chap_texts[chap_id] = pdf_to_text(pdf_path, cache_path)

    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    for chap_id_str, topic_num in TOPICS_TO_EXTRACT:
        chap_id = int(chap_id_str)
        if chap_id not in chap_texts:
            print(f"No text for chapter {chap_id}, skipping topic {topic_num}")
            continue
        content = chap_texts[chap_id]
        text = extract_topic_text(content, topic_num)
        if not text:
            print(f"Topic text not found: Chapter {chap_id}, Topic {topic_num}")
            continue
        try:
            cur.execute("""
                UPDATE public.topics
                SET full_text = %s
                WHERE chapter_id = %s AND topic_number = %s
            """, (text, chap_id, topic_num))
            print(f"Updated Chapter {chap_id} Topic {topic_num}")
        except Exception as e:
            print(f"Error updating Chapter {chap_id} Topic {topic_num}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done updating topics.")

if __name__ == "__main__":
    main()
