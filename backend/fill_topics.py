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
    155: {  # Chemistry Class 11 - Thermodynamics
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Thermodynamics.pdf",
        "ocr_cache": r"ocr_cache\Thermodynamics_11.txt"
    },
    158: {  # Chemistry Class 12 - Aldehydes, Ketones And Carboxylic Acid
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 12\Aldehydes, Ketones And Carboxylic Acid.pdf",
        "ocr_cache": r"ocr_cache\Aldehydes_Ketones_Carboxylic_12.txt"
    },
    174: {  # Maths Class 12 - Probability
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Maths\Class 12\Probability.pdf",
        "ocr_cache": r"ocr_cache\Probability_12.txt"
    },
    181: {  # Maths Class 12 - Continuity And Differentiability
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Maths\Class 12\Contunuity And Differentiability.pdf",
        "ocr_cache": r"ocr_cache\Continuity_Differentiability_12.txt"
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

# List of (chapter_id, topic_number) pairs to extract & update (adjust per your topics)
TOPICS_TO_EXTRACT = [
    # Example entries, replace or extend with your actual topic numbers
    ('155', '5.1'), ('155', '5.2'), # Thermodynamics topics
    ('158', '8.1'), ('158', '8.2'), # Aldehydes, Ketones topics
    ('174', '14.1'), ('174', '14.2'), # Probability topics
    ('181', '6.1'), ('181', '6.2'), # Continuity topics
]

def extract_topic_text(content, topic_number):
    pattern = re.compile(
        rf'^\s*{re.escape(topic_number)}\s*.*?(?=^\s*\d+(\.\d+)*\s*|\Z)', re.DOTALL | re.MULTILINE)
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

    print(f"Processing {len(TOPICS_TO_EXTRACT)} topics...")
    for t in TOPICS_TO_EXTRACT:
        print(t)

    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    for chap_id_str, topic_num in TOPICS_TO_EXTRACT:
        chap_id = int(chap_id_str)
        if chap_id not in chap_texts:
            print(f"No text for chapter {chap_id}, skipping topic {topic_num}")
            continue
        content = chap_texts[chap_id]
        text = extract_topic_text(content, topic_num)
        if text:
            print(f"Extracted text for Chapter {chap_id} Topic {topic_num} — length {len(text)} chars")
        else:
            print(f"No text found for Chapter {chap_id} Topic {topic_num}")
            continue
        try:
            cur.execute("""
                UPDATE public.topics
                SET full_text = %s
                WHERE chapter_id = %s AND topic_number = %s
            """, (text, chap_id, topic_num))
            print(f"Updated Chapter {chap_id} Topic {topic_num}")
        except Exception as e:
            print(f"Failed to update Chapter {chap_id} Topic {topic_num}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
