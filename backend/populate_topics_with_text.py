import os
import re
import psycopg2
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

# ======= 1. UPDATE THESE PATHS FOR YOUR SYSTEM =======
# This is now the main folder for all your books
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
# Path to the Poppler binary folder
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
# Path to the Tesseract executable
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# =======================================================

# --- Load secrets and configure Tesseract ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_ocr_text(pdf_path, poppler_path, dpi=300):
    """ (This function is unchanged) """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    print(f"Converting PDF pages to images ...")
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    print(f"Found {len(images)} pages ... Running OCR ...")
    all_text = []
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        text = text.replace('-\n', '')
        all_text.append(text)
    print("OCR extraction complete.")
    return "\n".join(all_text)

def extract_topics(chapter_text):
    """ (This function is unchanged) """
    heading_re = re.compile(r'^(\d+(?:\.\d+)+)\s+([^\n]+)', re.MULTILINE)
    matches = list(heading_re.finditer(chapter_text))
    topics = []
    for i, match in enumerate(matches):
        topic_num = match.group(1)
        topic_title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(chapter_text)
        content = chapter_text[start:end].strip()
        topics.append({'topic_number': topic_num, 'title': topic_title, 'content': content})
    return topics

def extract_questions(chapter_text):
    """ (This function is unchanged) """
    exercises_pat = re.compile(r'EXERCISES(.+)', re.DOTALL | re.IGNORECASE)
    ex_match = exercises_pat.search(chapter_text)
    if not ex_match:
        print('  - No EXERCISES section found.')
        return []
    exercises_text = ex_match.group(1)
    question_pat = re.compile(r'(\d+\.\d+|\d+\.)\s*-\s*(.+?)(?=\n\d+\.\d+|\n\d+\.|\n\n|$)', re.DOTALL)
    raw_questions = question_pat.findall(exercises_text)
    questions = []
    for qnum, qtext in raw_questions:
        questions.append({'question_number': qnum.strip('.'), 'question_text': qtext.strip()})
    return questions

def update_topics_in_db(cursor, topics, chapter_id):
    """ Updates the 'full_text' for topics that already exist in the database. """
    updated_count = 0
    for topic in topics:
        try:
            cursor.execute(
                "UPDATE topics SET full_text = %s, name = %s WHERE chapter_id = %s AND topic_number = %s",
                (topic['content'], topic['title'], chapter_id, topic['topic_number'])
            )
            if cursor.rowcount > 0:
                updated_count += 1
        except Exception as e:
            print(f"    [ERROR] Failed to update topic {topic['topic_number']}: {e}")
    print(f"  - Successfully updated {updated_count} topics in the database.")

def insert_questions_into_db(cursor, questions, chapter_id):
    """ Inserts extracted questions into the 'question_bank' table. """
    inserted_count = 0
    cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
    
    for q in questions:
        try:
            cursor.execute(
                "INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
                (chapter_id, q['question_number'], q['question_text'])
            )
            inserted_count += 1
        except Exception as e:
            print(f"    [ERROR] Failed to insert question {q['question_number']}: {e}")
    print(f"  - Successfully inserted {inserted_count} questions into the database.")

def main():
    conn = None
    try:
        print("Connecting to Supabase database...")
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        
        # Get all chapters from the database to create a lookup map
        cursor.execute("SELECT name, id FROM chapters")
        chapter_map = {name: chapter_id for name, chapter_id in cursor.fetchall()}

        # --- THIS IS THE NEW AUTOMATION LOOP ---
        for root, dirs, files in os.walk(PDF_ROOT_FOLDER):
            for filename in files:
                if filename.lower().endswith('.pdf'):
                    pdf_path = os.path.join(root, filename)
                    chapter_name_from_file = os.path.splitext(filename)[0]
                    
                    print(f"\n--- Processing: {pdf_path} ---")
                    
                    # Find the chapter_id for this file
                    target_chapter_id = chapter_map.get(chapter_name_from_file)
                    if not target_chapter_id:
                        print(f"  [WARNING] Chapter '{chapter_name_from_file}' not found in the database. Skipping.")
                        continue
                        
                    # 1. OCR (Your logic)
                    ocr_text = pdf_to_ocr_text(pdf_path, poppler_path)
                    
                    # 2. Extraction (Your logic)
                    topics = extract_topics(ocr_text)
                    print(f"  - Extracted {len(topics)} topics.")
                    questions = extract_questions(ocr_text)
                    print(f"  - Extracted {len(questions)} questions.")
                    
                    # 3. Database Upload
                    update_topics_in_db(cursor, topics, target_chapter_id)
                    insert_questions_into_db(cursor, questions, target_chapter_id)
                    
                    # Commit changes for each chapter
                    conn.commit()
                    print(f"  - Saved changes for '{chapter_name_from_file}' to Supabase.")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] A problem occurred: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("\nDatabase connection closed. Script finished.")

if __name__ == "__main__":
    main()