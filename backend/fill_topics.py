import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract


# Uncomment and set this if your Tesseract executable is in a custom location (Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"


load_dotenv()
DB_CONN = os.getenv("SUPABASE_CONNECTION_STRING")


if not DB_CONN:
    raise ValueError("Missing SUPABASE_CONNECTION_STRING in environment variables.")


CHAPTER_CONFIG = {
    155: {
        "pdf": r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise\\Chemistry\\Class 11\\Thermodynamics.pdf",
        "ocr_cache": r"ocr_cache\\Thermodynamics_11.txt"
    },
    158: {
        "pdf": r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise\\Chemistry\\Class 12\\Aldehydes, Ketones And Carboxylic Acid.pdf",
        "ocr_cache": r"ocr_cache\\Aldehydes_Ketones_Carboxylic_12.txt"
    },
    174: {
        "pdf": r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise\\Maths\\Class 12\\Probability.pdf",
        "ocr_cache": r"ocr_cache\\Probability_12.txt"
    },
    181: {
        "pdf": r"C:\\Users\\daksh\\OneDrive\\Dokumen\\ai-tutor\\backend\\NCERT_PCM_ChapterWise\\Maths\\Class 12\\Contunuity And Differentiability.pdf",
        "ocr_cache": r"ocr_cache\\Continuity_Differentiability_12.txt"
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


TOPICS_TO_EXTRACT = [
    ('155', '5.1'), ('155', '5.2'),
    ('158', '8.1'), ('158', '8.2'),
    ('174', '13.1'), ('174', '13.2'),
    ('181', '5.1'), ('181', '5.2'),
]


def extract_topic_text(content, topic_number):
    # Adjust regex to allow flexible spaces and optional dots for topic numbers
    # Pattern will include the topic number line then everything until next "major" topic number, possibly like 1, 2, 3, or subtopics like 5.2, 5.3 etc.
    flexible_num = re.escape(topic_number).replace(r"\.", r"\s*\.?\s*")
    # We capture from the line starting with topic_number until before next line starting with digit(s). possibly with dot notation or end of file
    pattern = re.compile(
        rf'^\s*{flexible_num}[\s\S]*?(?=^\s*\d+(\.\d+)*\s|^\s*$)', re.MULTILINE)
    match = pattern.search(content)
    if match:
        # To avoid partial capture beyond a wider section, trim trailing spaces
        return match.group().strip()
    return ""


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
            snippet = text[:300].replace('\n', ' ').replace('\r', '')
            print(f"Extracted text for Chapter {chap_id} Topic {topic_num} — length {len(text)} chars. Snippet: {snippet}...")
            try:
                cur.execute("""
                    UPDATE public.topics
                    SET full_text = %s
                    WHERE chapter_id = %s AND topic_number = %s
                """, (text, chap_id, topic_num))
                print(f"Updated Chapter {chap_id} Topic {topic_num}")
            except Exception as e:
                print(f"Failed to update Chapter {chap_id} Topic {topic_num}: {e}")
        else:
            # Show context around expected topic header for debugging
            pattern_debug = re.compile(
                rf'.{{0,50}}{re.escape(topic_num)}.{{0,50}}', re.MULTILINE | re.DOTALL | re.IGNORECASE)
            found_debug = pattern_debug.findall(content)
            print(f"No text found for Chapter {chap_id} Topic {topic_num}. Context samples: {found_debug if found_debug else 'None found'}")


    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
