import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
from pdf2image import convert_from_path
import pytesseract

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Documents\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Documents\ai-tutor\backend\final_verified_topics.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Documents\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Documents\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

# --- This is the list of the 4 chapters the script will process ---
CHAPTER_CONFIG = {
    155: {
        "pdf_filename": "Thermodynamics.pdf",
        "subject": "Chemistry",
        "class": "Class 11",
    },
    158: {
        "pdf_filename": "Aldehydes, Ketones And Carboxylic Acid.pdf",
        "subject": "Chemistry",
        "class": "Class 12",
    },
    174: {
        "pdf_filename": "Probability.pdf",
        "subject": "Maths",
        "class": "Class 12",
    },
    181: {
        "pdf_filename": "Contunuity And Differentiability.pdf",
        "subject": "Maths",
        "class": "Class 12",
    }
}


def log(msg: str):
    print(msg, flush=True)

def pdf_to_text(pdf_path, cache_folder):
    """Performs OCR on a PDF and caches the result."""
    cache_path = os.path.join(cache_folder, os.path.basename(pdf_path) + ".txt")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    log(f"  [OCR] Processing {os.path.basename(pdf_path)} ...")
    pages = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    text = "\n".join(pytesseract.image_to_string(img) for img in pages)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"  [CACHE SAVED] {os.path.basename(cache_path)}")
    return text

def extract_all_topics_with_split(chapter_text, topics_for_chapter_df):
    """Finds all topic numbers from the CSV and uses them to segment the text."""
    # Get a sorted list of topic numbers for this specific chapter
    topic_numbers = sorted(topics_for_chapter_df['heading_number'].tolist(), key=lambda x: [int(i) for i in x.split('.') if i.isdigit()])
    
    heading_pattern = re.compile(r'^\s*(%s)\s+' % '|'.join([re.escape(tn) for tn in topic_numbers]), re.MULTILINE)
    matches = list(heading_pattern.finditer(chapter_text))
    
    topic_locations = {match.group(1).strip(): match.start() for match in matches}
    log(f"  - Found {len(topic_locations)} of {len(topics_for_chapter_df)} topic headings in the OCR text.")
    
    extracted_topics = []
    for topic_num in topic_numbers:
        start_pos = topic_locations.get(topic_num)
        if start_pos is not None:
            end_pos = len(chapter_text)
            for next_num, next_pos in topic_locations.items():
                if next_pos > start_pos and next_pos < end_pos:
                    end_pos = next_pos
            content = chapter_text[start_pos:end_pos].strip()
            extracted_topics.append({'topic_number': topic_num, 'content': content})
            
    return extracted_topics

def main():
    try:
        master_df = pd.read_csv(CSV_PATH, dtype=str).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        log(f"[INFO] Loaded master topic list from {CSV_PATH}.")
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {CSV_PATH}")
        return

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cur = conn.cursor()

        for chap_id, config in CHAPTER_CONFIG.items():
            pdf_filename = config["pdf_filename"]
            pdf_path = os.path.join(PDF_ROOT_FOLDER, config["subject"], config["class"], pdf_filename)
            
            log(f"\n--- Processing: {pdf_filename} ---")
            
            if not os.path.exists(pdf_path):
                log(f"  [ERROR] PDF not found at {pdf_path}. Skipping.")
                continue

            # Filter the master CSV to get all topics for this specific chapter
            topics_for_this_chapter_df = master_df[master_df['chapter_file'] == pdf_filename]
            if topics_for_this_chapter_df.empty:
                log(f"  [WARNING] No topics found in the CSV for {pdf_filename}. Skipping.")
                continue
            
            # Run OCR to get the full text
            full_text = pdf_to_text(pdf_path, OCR_CACHE_FOLDER)
            
            # Extract all topics using the filtered list
            extracted_topics = extract_all_topics_with_split(full_text, topics_for_this_chapter_df)
            
            log(f"  - Extracted content for {len(extracted_topics)} topics.")
            
            # Update the database
            for topic in extracted_topics:
                try:
                    cur.execute(
                        "UPDATE public.topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (topic['content'], chap_id, topic['topic_number'])
                    )
                except Exception as e:
                    log(f"  -> Failed to update Chapter {chap_id} Topic {topic['topic_number']}: {e}")
            
            conn.commit()
            log(f"  -> Successfully sent {len(extracted_topics)} updates to the database.")

    except Exception as e:
        log(f"A critical error occurred: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
        log("\nDone.")

if __name__ == "__main__":
    main()