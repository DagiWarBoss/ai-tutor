import os
import fitz  # PyMuPDF
import psycopg2
import re

# --- YOUR SUPABASE CREDENTIALS (IPv4 Compatible) ---
# Replace these with your actual database details from Supabase
# Use the "Transaction Pooler" credentials
DB_HOST = "aws-0-ap-south-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.fwqeskdcauwbowsbycnf" # Make sure this is your correct pooler user
DB_PASSWORD = "your-database-password"     # PASTE YOUR SAVED PASSWORD HERE
DB_PORT = "5432"

# --- CONFIGURATION ---
# IMPORTANT: Update this to the path of your main folder
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise" 
# IMPORTANT: Set the class level for the books being processed
CLASS_LEVEL = 12 # Change to 11 or another value as needed

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
            level, title, page = item
            match = re.match(r"^\s*([\d\.]+)\s*(.*)", title)
            if match:
                topic_number, topic_name = match.groups()
                topics.append({
                    "topic_number": topic_number.strip(),
                    "topic_name": topic_name.strip()
                })
        return topics
    except Exception as e:
        print(f"    - Error processing {os.path.basename(pdf_path)}: {e}")
        return []

def main():
    """Walks through the folder structure and populates the database."""
    conn = None
    cur = None
    conn_string = f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASSWORD}' port='{DB_PORT}'"
    
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        print("✅ Successfully connected to the database.")

        for subject_name in os.listdir(PDF_ROOT_FOLDER):
            subject_path = os.path.join(PDF_ROOT_FOLDER, subject_name)
            if os.path.isdir(subject_path):
                print(f"\nProcessing Subject: {subject_name} (Class {CLASS_LEVEL})")
                
                cur.execute(
                    "INSERT INTO subjects (name, class_level) VALUES (%s, %s) ON CONFLICT (name, class_level) DO NOTHING RETURNING id",
                    (subject_name, CLASS_LEVEL)
                )
                result = cur.fetchone()
                if result is None:
                    cur.execute("SELECT id FROM subjects WHERE name = %s AND class_level = %s", (subject_name, CLASS_LEVEL))
                    result = cur.fetchone()
                
                subject_id = result[0]
                print(f"  -> Subject '{subject_name}' has ID: {subject_id}")

                chapter_number_counter = 1
                for filename in sorted(os.listdir(subject_path)):
                    if filename.endswith(".pdf"):
                        chapter_name = filename.replace('.pdf', '')
                        print(f"  -> Processing Chapter: {chapter_name}")
                        
                        pdf_path = os.path.join(subject_path, filename)
                        topics_data = extract_topics_from_pdf(pdf_path)
                        
                        # =============================================================
                        # THIS IS THE CORRECTED LINE
                        # It no longer tries to insert a 'full_text' column
                        # =============================================================
                        cur.execute(
                            "INSERT INTO chapters (subject_id, chapter_number, name) VALUES (%s, %s, %s) RETURNING id",
                            (subject_id, chapter_number_counter, chapter_name)
                        )
                        chapter_id = cur.fetchone()[0]
                        chapter_number_counter += 1

                        if topics_data:
                            print(f"    - Found {len(topics_data)} topics. Inserting...")
                            for topic_info in topics_data:
                                cur.execute(
                                    "INSERT INTO topics (chapter_id, topic_number, name) VALUES (%s, %s, %s)",
                                    (chapter_id, topic_info['topic_number'], topic_info['topic_name'])
                                )
                        else:
                            print("    - No topics found or extracted for this chapter.")

        conn.commit()
        print("\n✅ All data has been successfully inserted and committed.")

    except FileNotFoundError:
        print(f"❌ Error: The root folder '{PDF_ROOT_FOLDER}' was not found. Please check the path.")
    except psycopg2.Error as e:
        print(f"❌ A database error occurred: {e}")
        if conn:
            conn.rollback() # Roll back the transaction on error
            print("\n  The transaction has been rolled back.")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("\nScript finished.")


if __name__ == '__main__':
    main()
