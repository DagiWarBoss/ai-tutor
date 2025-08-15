import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
pdf_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Some Basic Concepts Of Chemistry.pdf"
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ocr_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"
topic_csv_path = "topics_output.csv"
question_csv_path = "questions_output.csv"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = tesseract_path
os.makedirs("ocr_cache", exist_ok=True)


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

TOPICS_TO_EXTRACT = [
    ('155', '5.1'), ('155', '5.2'),
    ('158', '8.1'), ('158', '8.2'),
    ('174', '13.1'), ('174', '13.2'),
    ('181', '5.1'), ('181', '5.2'),
]

def pdf_to_text(pdf_path, cache_path):
    """ (This function is unchanged) """
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

def extract_all_topics_with_split(chapter_text):
    """
    --- THIS IS THE NEW, MORE RELIABLE LOGIC ---
    Finds all topic numbers and uses them as split points to segment the text.
    """
    # Find all potential topic numbers (e.g., 5.1, 5.2.1) at the start of a line
    heading_pattern = re.compile(r'^\s*(\d+(?:\.\d+)*)\s+', re.MULTILINE)
    
    # Find the locations of all headings
    matches = list(heading_pattern.finditer(chapter_text))
    topic_locations = {match.group(1).strip(): match.start() for match in matches}
    
    extracted_content = {}
    
    # Sort the locations to process them in order
    sorted_locations = sorted(topic_locations.items(), key=lambda item: item[1])
    
    for i, (topic_num, start_pos) in enumerate(sorted_locations):
        # The end position is the start of the next topic, or the end of the text
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
            print(f"PDF not found: {pdf_path}")
            continue
        chap_texts[chap_id] = pdf_to_text(pdf_path, cache_path)

    print(f"\nProcessing {len(TOPICS_TO_EXTRACT)} specific topics...")
    
    conn = None
    try:
        conn = psycopg2.connect(DB_CONN)
        cur = conn.cursor()

        for chap_id_str, topic_num_to_find in TOPICS_TO_EXTRACT:
            chap_id = int(chap_id_str)
            if chap_id not in chap_texts:
                print(f"No text for chapter {chap_id}, skipping topic {topic_num_to_find}")
                continue
            
            # Extract all topics from the chapter text first
            all_extracted_topics = extract_all_topics_with_split(chap_texts[chap_id])
            
            # Now, find the specific topic we are looking for
            text = all_extracted_topics.get(topic_num_to_find)
            
            if text:
                snippet = text[:300].replace('\n', ' ').replace('\r', '')
                print(f"\nExtracted text for Chapter {chap_id} Topic {topic_num_to_find} — length {len(text)} chars.")
                print(f"Snippet: {snippet}...")
                try:
                    cur.execute("""
                        UPDATE public.topics
                        SET full_text = %s
                        WHERE chapter_id = %s AND topic_number = %s
                    """, (text, chap_id, topic_num_to_find))
                    print(f"  -> Update command sent for Chapter {chap_id} Topic {topic_num_to_find}")
                except Exception as e:
                    print(f"  -> Failed to update Chapter {chap_id} Topic {topic_num_to_find}: {e}")
            else:
                print(f"\nNo text found for Chapter {chap_id} Topic {topic_num_to_find}.")
        
        conn.commit()

    except Exception as e:
        print(f"A critical error occurred: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
        print("\nDone.")

if __name__ == "__main__":
    main()