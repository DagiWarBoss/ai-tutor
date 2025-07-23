import os
import fitz  # PyMuPDF
import psycopg2
import psycopg2.extras  # For batch inserting
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This script will load credentials from the .env file in the 'backend' directory.
load_dotenv()

# --- YOUR SUPABASE CREDENTIALS (from .env file) ---
# Using os.getenv without defaults makes the script fail clearly if a variable is missing.
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- CONFIGURATION ---
# IMPORTANT: This should be the name of the folder inside 'backend' that contains your subject folders.
# IMPORTANT: Set the class level for the books being processed
CLASS_LEVEL = 12  # Change to 11 or another value as needed

TXT_ROOT_FOLDER = "txt_outputs"  # Folder containing the pre-extracted .txt files

def extract_topics_from_pdf(pdf_path):
    """Extracts a list of topics from a chapter PDF's table of contents."""
    topics = []
            return []

        for item in toc:
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
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + " "
        return full_text.strip()
    except Exception as e:
        print(f"    - Error extracting full text from {os.path.basename(pdf_path)}: {e}")
        print("❌ Error: Database credentials not found. Please ensure DB_HOST, DB_PASSWORD, etc., are set in your .env file.")
        return

    script_dir = os.path.dirname(__file__)
    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)

    try:
        # Use a 'with' statement for the connection and cursor to ensure they are always closed.
        # The 'with' block also handles transactions (commit on success, rollback on error).
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        ) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
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
                                # Construct the correct path to the corresponding .txt file
                                txt_path = os.path.join(script_dir, TXT_ROOT_FOLDER, subject_name, f"{chapter_name}.txt")

                                # Prioritize reading from a pre-extracted .txt file for speed.
                                if os.path.exists(txt_path):
                                    print(f"    - Found '{os.path.basename(txt_path)}', reading text from file.")
                                    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        full_chapter_text = f.read()
                                else:
                                    print(f"    - No .txt file found, extracting full text from PDF.")
                                    full_chapter_text = extract_full_text_from_pdf(pdf_path)

                                # Topic extraction ALWAYS uses the PDF to get the structured Table of Contents.
                                topics_data = extract_topics_from_pdf(pdf_path)

                                # Insert Chapter and get its ID
                                cur.execute(
                                    "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                    (subject_id, chapter_number_counter, chapter_name, full_chapter_text),
                                )
                                chapter_id = cur.fetchone()[0]
                                chapter_number_counter += 1

                                # Insert all topics for this chapter using a more efficient batch method
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
        print("   The transaction has been rolled back.")
    print("\nScript finished.")

if __name__ == '__main__':
    main()
