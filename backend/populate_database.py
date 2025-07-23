import os
import fitz  # PyMuPDF
import psycopg2
import psycopg2.extras  # For batch inserting
import re
from dotenv import load_dotenv

# --- Explicitly load the .env file from the backend directory ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- SECURELY GET CREDENTIALS FROM ENVIRONMENT ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- CONFIGURATION ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CLASS_LEVEL = 12  # Change to 11 or another value as needed

def extract_topics_from_pdf(pdf_path):
    """Extracts a list of topics from a chapter PDF's table of contents."""
    topics = []
    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        if not toc:
            print(f"    - Warning: No table of contents found in {os.path.basename(pdf_path)}.")
            return []

        print(f"    - DEBUG: Reading Table of Contents for {os.path.basename(pdf_path)}...")
        for item in toc:
            # --- THIS IS THE NEW DEBUG LINE ---
            print(f"      -> Found TOC item: {item}")

            level, title, page = item
            match = re.match(r"^\s*([\d\.]+)\s*(.*)", title)
            if match:
                topic_number, topic_name = match.groups()
                topics.append({"topic_number": topic_number.strip(), "topic_name": topic_name.strip()})
        return topics
    except Exception as e:
        print(f"    - Error processing TOC for {os.path.basename(pdf_path)}: {e}")
        return []

def extract_full_text_from_pdf(pdf_path):
    """Extracts the full text content from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + " "
        return full_text.strip()
    except Exception as e:
        print(f"    - Error extracting full text from {os.path.basename(pdf_path)}: {e}")
        return ""

def main():
    """Walks through the folder structure and populates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Please ensure DB_HOST, DB_PASSWORD, etc., are set in your .env file.")
        return

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)

    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        ) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                for subject_name in os.listdir(pdf_root_full_path):
                    subject_path = os.path.join(pdf_root_full_path, subject_name)
                    if os.path.isdir(subject_path):
                        print(f"\nProcessing Subject: '{subject_name}' (Class {CLASS_LEVEL})")

                        upsert_subject_query = """
                            WITH ins AS (
                                INSERT INTO subjects (name, class_level)
                                VALUES (%s, %s)
                                ON CONFLICT (name, class_level) DO NOTHING
                                RETURNING id
                            )
                            SELECT id FROM ins
                            UNION ALL
                            SELECT id FROM subjects WHERE name = %s AND class_level = %s LIMIT 1;
                        """
                        cur.execute(
                            upsert_subject_query,
                            (subject_name, CLASS_LEVEL, subject_name, CLASS_LEVEL),
                        )
                        subject_id = cur.fetchone()[0]
                        print(f"  -> Subject '{subject_name}' has ID: {subject_id}")

                        chapter_number_counter = 1
                        for filename in sorted(os.listdir(subject_path)):
                            if filename.lower().endswith(".pdf"):
                                chapter_name = os.path.splitext(filename)[0].strip()

                                cur.execute("SELECT id FROM chapters WHERE subject_id = %s AND name = %s", (subject_id, chapter_name))
                                if cur.fetchone():
                                    print(f"  -> Chapter '{chapter_name}' already exists. Skipping.")
                                    continue

                                print(f"  -> Processing NEW Chapter: {chapter_name}")

                                pdf_path = os.path.join(subject_path, filename)
                                topics_data = extract_topics_from_pdf(pdf_path)
                                full_chapter_text = extract_full_text_from_pdf(pdf_path)

                                cur.execute(
                                    "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                    (subject_id, chapter_number_counter, chapter_name, full_chapter_text),
                                )
                                chapter_id = cur.fetchone()[0]
                                chapter_number_counter += 1

                                if topics_data:
                                    print(f"    - Found {len(topics_data)} topics. Inserting in a single batch...")
                                    topic_values = [
                                        (chapter_id, topic['topic_number'], topic['topic_name'])
                                        for topic in topics_data
                                    ]
                                    psycopg2.extras.execute_values(
                                        cur,
                                        "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s",
                                        topic_values
                                    )
                                else:
                                    print("    - No topics found or extracted for this chapter.")

                print("\n✅ All data has been successfully inserted and committed.")

    except FileNotFoundError:
        print(f"❌ Error: The root folder '{pdf_root_full_path}' was not found. Please check the path in the script.")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print("  The transaction has been rolled back.")
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
