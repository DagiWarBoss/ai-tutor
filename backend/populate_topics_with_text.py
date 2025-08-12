import os
import re
import csv
import psycopg2 # For connecting to Supabase
from dotenv import load_dotenv # For loading secrets
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

# ======= 1. UPDATE THESE PATHS AND CHAPTER DETAILS FOR YOUR SYSTEM =======
# --- File Paths ---
pdf_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Some Basic Concepts Of Chemistry.pdf"
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ocr_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt" # For saving a backup of the OCR text

# --- Chapter Details (Must match your database) ---
TARGET_CHAPTER_NAME = "Some Basic Concepts Of Chemistry"
TARGET_CHAPTER_ID = 1 # The ID of this chapter in your 'chapters' table

# =======================================================================

# --- Load secrets and configure Tesseract ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_ocr_text(pdf_path, poppler_path, dpi=300):
    """
    (This function is unchanged)
    Converts a PDF to raw text using OCR.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    print(f"Converting PDF pages to images ...")
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    print(f"Found {len(images)} pages ... Running OCR ...")
    all_text = []
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        text = text.replace('-\n', '')  # Clean up broken words
        all_text.append(text)
    print("OCR extraction complete.")
    return "\n".join(all_text)

def extract_topics(chapter_text):
    """
    (This function is unchanged)
    Extracts topics and their content using regex.
    """
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
    """
    (This function is unchanged)
    Extracts exercise questions using regex.
    """
    exercises_pat = re.compile(r'EXERCISES(.+)', re.DOTALL | re.IGNORECASE)
    ex_match = exercises_pat.search(chapter_text)
    if not ex_match:
        print('No EXERCISES section found!')
        return []
    exercises_text = ex_match.group(1)
    question_pat = re.compile(r'(\d+\.\d+|\d+\.)\s*-\s*(.+?)(?=\n\d+\.\d+|\n\d+\.|\n\n|$)', re.DOTALL)
    raw_questions = question_pat.findall(exercises_text)
    questions = []
    for qnum, qtext in raw_questions:
        questions.append({'question_number': qnum.strip('.'), 'question_text': qtext.strip()})
    return questions

# --- NEW FUNCTIONS TO INTERACT WITH SUPABASE ---

def update_topics_in_db(cursor, topics, chapter_id):
    """
    Updates the 'full_text' for topics that already exist in the database.
    """
    print(f"\nUpdating {len(topics)} topics in the database...")
    updated_count = 0
    for topic in topics:
        try:
            cursor.execute(
                "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                (topic['content'], chapter_id, topic['topic_number'])
            )
            if cursor.rowcount > 0:
                updated_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to update topic {topic['topic_number']}: {e}")
    print(f"Successfully updated {updated_count} topics.")

def insert_questions_into_db(cursor, questions, chapter_id):
    """
    Inserts extracted questions into the 'question_bank' table.
    """
    print(f"\nInserting {len(questions)} questions into the database...")
    inserted_count = 0
    # To avoid duplicates, first delete any existing questions for this chapter
    cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
    print(f"  - Cleared any existing questions for Chapter ID: {chapter_id}")
    
    for q in questions:
        try:
            cursor.execute(
                "INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
                (chapter_id, q['question_number'], q['question_text'])
            )
            inserted_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to insert question {q['question_number']}: {e}")
    print(f"Successfully inserted {inserted_count} questions.")


if __name__ == "__main__":
    # Step 1: OCR conversion (unchanged)
    ocr_text = pdf_to_ocr_text(pdf_path, poppler_path, dpi=300)
    with open(ocr_txt_path, "w", encoding="utf-8") as f:
        f.write(ocr_text)
    print(f"OCR text written to {ocr_txt_path}")

    # Step 2: Topic and Question extraction (unchanged)
    topics = extract_topics(ocr_text)
    print(f"\nExtracted {len(topics)} topics.")
    questions = extract_questions(ocr_text)
    print(f"Extracted {len(questions)} questions.")

    # Step 3: Connect to Supabase and upload the data
    conn = None
    try:
        print("\nConnecting to Supabase database...")
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        
        # Update the topics in the DB
        update_topics_in_db(cursor, topics, TARGET_CHAPTER_ID)
        
        # Insert the questions into the DB
        insert_questions_into_db(cursor, questions, TARGET_CHAPTER_ID)
        
        # Commit all changes
        conn.commit()
        print("\n[SUCCESS] All data has been successfully saved to Supabase.")

    except Exception as e:
        print(f"\n[DATABASE ERROR] An error occurred: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")