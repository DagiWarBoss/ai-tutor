import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
# This script will ONLY process the 4 chapters defined in CHAPTER_CONFIG below
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

# --- This is the list of the 4 chapters the script will process ---
CHAPTER_CONFIG = {
    155: {
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Thermodynamics.pdf",
        "ocr_cache": r"ocr_cache\Thermodynamics_11.txt"
    },
    158: {
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 12\Aldehydes, Ketones And Carboxylic Acid.pdf",
        "ocr_cache": r"ocr_cache\Aldehydes_Ketones_Carboxylic_12.txt"
    },
    174: {
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Maths\Class 12\Probability.pdf",
        "ocr_cache": r"ocr_cache\Probability_12.txt"
    },
    181: {
        "pdf": r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Maths\Class 12\Contunuity And Differentiability.pdf",
        "ocr_cache": r"ocr_cache\Continuity_Differentiability_12.txt"
    }
}

# This is the list of specific topics to find within those chapters
TOPICS_TO_EXTRACT = [
    ('155', '5.1'), ('155', '5.2'),
    ('158', '8.1'), ('158', '8.2'),
    ('174', '13.1'), ('174', '13.2'),
    ('181', '5.1'), ('181', '5.2'),
]

def log(msg: str):
    print(msg, flush=True)

def pdf_to_text(pdf_path, cache_path):
    """Performs OCR on a PDF and caches the result."""
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    log(f"[OCR] Processing {os.path.basename(pdf_path)} ...")
    pages = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    text = "\n".join(pytesseract.image_to_string(img) for img in pages)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"[CACHE SAVED] {os.path.basename(cache_path)}")
    return text

def extract_all_topics_with_split(chapter_text):
    """Finds all topic numbers and uses them as split points to segment the text."""
    heading_pattern = re.compile(r'^\s*(\d+(?:\.\d+)*)\s+', re.MULTILINE)
    matches = list(heading_pattern.finditer(chapter_text))
    topic_locations = {match.group(1).strip(): match.start() for match in matches}
    
    extracted_content = {}
    sorted_locations = sorted(topic_locations.items(), key=lambda item: item[1])
    
    for i, (topic_num, start_pos) in enumerate(sorted_locations):
        end_pos = sorted_locations[i + 1][1] if i + 1 < len(sorted_locations) else len(chapter_text)
        content = chapter_text[start_pos:end_pos].strip()
        extracted_content[topic_num] = content
        
    return extracted_content

def main():
    chap_texts = {}
    for chap_id, paths in CHAPTER_CONFIG.items():
        pdf_path = paths["pdf"]
        cache_path = paths["ocr_cache"]
        if not os.path.exists(pdf_path):
            log(f"PDF not found: {pdf_path}")
            continue
        chap_texts[chap_id] = pdf_to_text(pdf_path, cache_path)

    log(f"\nProcessing {len(TOPICS_TO_EXTRACT)} specific topics...")
    
    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cur = conn.cursor()

        for chap_id_str, topic_num_to_find in TOPICS_TO_EXTRACT:
            chap_id = int(chap_id_str)
            if chap_id not in chap_texts:
                log(f"No text for chapter {chap_id}, skipping topic {topic_num_to_find}")
                continue
            
            # Extract all topics from the chapter text first
            all_extracted_topics = extract_all_topics_with_split(chap_texts[chap_id])
            
            # Now, find the specific topic we are looking for
            text = all_extracted_topics.get(topic_num_to_find)
            
            if text:
                snippet = text[:300].replace('\n', ' ').replace('\r', '')
                log(f"\nExtracted text for Chapter {chap_id} Topic {topic_num_to_find} — length {len(text)} chars.")
                log(f"Snippet: {snippet}...")
                try:
                    cur.execute(
                        "UPDATE public.topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (text, chap_id, topic_num_to_find)
                    )
                    log(f"  -> Update command sent for Chapter {chap_id} Topic {topic_num_to_find}")
                except Exception as e:
                    log(f"  -> Failed to update Chapter {chap_id} Topic {topic_num_to_find}: {e}")
            else:
                log(f"\nNo text found for Chapter {chap_id} Topic {topic_num_to_find}.")
        
        conn.commit()

    except Exception as e:
        log(f"A critical error occurred: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
        log("\nDone.")

if __name__ == "__main__":
    main()