import os
import fitz  # PyMuPDF
import psycopg2
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This script will load credentials from the .env file in the 'backend' directory.
load_dotenv()

# --- YOUR SUPABASE CREDENTIALS (from .env file) ---
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")

# --- CONFIGURATION ---
# IMPORTANT: This should be the name of the folder inside 'backend' that contains your subject folders.
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
# IMPORTANT: Set the class level for the books being processed
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

        for item in toc:
            # We treat every item in the TOC as a topic for this chapter
            level, title, page = item
            match = re.match(r"^\s*([\d\.]+)\s*(.*)", title)
            if match:
                topic_number, topic_name = match.groups()
                topics.append({"topic_number": topic_number.strip(), "topic_name": topic_name.strip()})
        return topics
    except Exception as e:
        print(f"    - Error processing {os.path.basename(pdf_path)}: {e}")
        return []

def extract_full_text_from_pdf(pdf_path):
    """Extracts the full text content from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            # Add a space between pages for better sentence separation
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

    conn_string = f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASSWORD}' port='{DB_PORT}'"
    conn = None
    cur = None

    # --- Step 1: Connect to the database ---
    try:
        print("Attempting to connect to the database...")
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        print("✅ Successfully connected to the database.")
    except psycopg2.OperationalError as e:
        print("\n❌ DATABASE CONNECTION FAILED. Please double-check your credentials in the .env file, especially the DB_PASSWORD.")
        print(f"   Error details: {e}")
        return # Stop the script if connection fails

    # --- Step 2: Process files and populate the database ---
    try:
        # Construct the full path to the PDF root folder
        pdf_root_full_path = os.path.join(os.path.dirname(__file__), PDF_ROOT_FOLDER)

        # Walk through the directory structure
        for subject_name in os.listdir(pdf_root_full_path):
            subject_path = os.path.join(pdf_root_full_path, subject_name)
            if os.path.isdir(subject_path):
                print(f"\nProcessing Subject: '{subject_name}' (Class {CLASS_LEVEL})")

                # Upsert Subject and get its ID. This is more efficient and robust.
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

                # Process each chapter PDF in the subject folder
                chapter_number_counter = 1
                for filename in sorted(os.listdir(subject_path)):
                    if filename.lower().endswith(".pdf"):
                        chapter_name = os.path.splitext(filename)[0].strip()

                        # Check if chapter already exists to make the script re-runnable
                        cur.execute("SELECT id FROM chapters WHERE subject_id = %s AND name = %s", (subject_id, chapter_name))
                        if cur.fetchone():
                            print(f"  -> Chapter '{chapter_name}' already exists. Skipping.")
                            chapter_number_counter += 1
                            continue

                        print(f"  -> Processing NEW Chapter: {chapter_name}")

                        pdf_path = os.path.join(subject_path, filename)
                        topics_data = extract_topics_from_pdf(pdf_path)
                        full_chapter_text = extract_full_text_from_pdf(pdf_path)

                        # Insert Chapter and get its ID
                        cur.execute(
                            "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                            (subject_id, chapter_number_counter, chapter_name, full_chapter_text),
                        )
                        chapter_id = cur.fetchone()[0]
                        chapter_number_counter += 1

                        # Insert all topics for this chapter
                        if topics_data:
                            print(f"    - Found {len(topics_data)} topics. Inserting...")
                            for topic_info in topics_data:
                                cur.execute("INSERT INTO topics (chapter_id, topic_number, name) VALUES (%s, %s, %s)", (chapter_id, topic_info["topic_number"], topic_info["topic_name"]))
                        else:
                            print("    - No topics found or extracted for this chapter.")

        conn.commit()
        print("\n✅ All data has been successfully inserted and committed.")

    except FileNotFoundError:
        print(f"❌ Error: The root folder '{pdf_root_full_path}' was not found. Please check the path in the script.")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("\nDatabase connection closed.")

if __name__ == '__main__':
    main()
