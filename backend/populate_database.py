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
TXT_CACHE_FOLDER = "txt_outputs"

def extract_topics_from_pdf(pdf_path):
    """
    Smarter topic extraction. First tries bookmarks (get_toc), if that fails,
    it manually scans the first few pages for topic-like text patterns.
    """
    try:
        doc = fitz.open(pdf_path)
        # --- METHOD 1: Try the fast bookmark method first ---
        toc = doc.get_toc()
        if toc:
            topics = []
            for item in toc:
                level, title, page = item
                match = re.match(r"^\s*([\d\.]+)\s*(.*)", title)
                if match:
                    topic_number, topic_name = match.groups()
                    if topic_name:
                        topics.append({"topic_number": topic_number.strip(), "topic_name": topic_name.strip()})
            if topics:
                print("    - Success: Extracted topics using bookmarks (TOC).")
                return topics

        # --- METHOD 2: If bookmarks fail, manually scan pages ---
        print("    - TOC bookmarks not found or empty. Scanning page text...")
        topics = []
        topic_pattern = re.compile(r"^\s*(\d+\.\d+(\.\d+)*)\s+(.*)", re.MULTILINE)
        
        for page_num in range(min(5, doc.page_count)):
            page_text = doc[page_num].get_text()
            matches = topic_pattern.findall(page_text)
            for match in matches:
                topic_number = match[0]
                topic_name = match[2].strip()
                if topic_name and len(topic_name) > 3:
                    topics.append({"topic_number": topic_number, "topic_name": topic_name})

        if topics:
             print(f"    - Success: Extracted {len(topics)} topics by scanning page text.")
        else:
             print(f"    - Warning: Could not find topics using any method for {os.path.basename(pdf_path)}.")
        
        seen = set()
        unique_topics = []
        for topic in topics:
            if topic['topic_name'] not in seen:
                seen.add(topic['topic_name'])
                unique_topics.append(topic)
        
        return unique_topics

    except Exception as e:
        print(f"    - Error processing TOC for {os.path.basename(pdf_path)}: {e}")
        return []


def get_full_text(pdf_path, cache_path):
    """
    Gets full text. Prioritizes reading from a cached .txt file.
    If not found, extracts from PDF and creates a .txt file for next time.
    """
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    print(f"    - Cache miss. Extracting text from PDF...")
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + " "
        
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"    - Saved text to cache: '{os.path.basename(cache_path)}'")
        
        return full_text.strip()
    except Exception as e:
        print(f"    - Error extracting full text from {os.path.basename(pdf_path)}: {e}")
        return ""

def main():
    """Walks through a simplified folder structure and populates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Ensure .env file is correct.")
        return

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)
    txt_cache_full_path = os.path.join(script_dir, TXT_CACHE_FOLDER)

    try:
        with psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        ) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                # Loop directly through subject folders
                for subject_name in sorted(os.listdir(pdf_root_full_path)):
                    subject_path = os.path.join(pdf_root_full_path, subject_name)
                    if os.path.isdir(subject_path):
                        print(f"\n===== Processing Subject: '{subject_name}' =====")

                        # Upsert Subject and get its ID (simplified query)
                        upsert_subject_query = """
                            WITH ins AS (INSERT INTO subjects (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id)
                            SELECT id FROM ins UNION ALL SELECT id FROM subjects WHERE name = %s LIMIT 1;
                        """
                        cur.execute(upsert_subject_query, (subject_name, subject_name))
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
                                cache_path = os.path.join(txt_cache_full_path, subject_name, f"{chapter_name}.txt")
                                
                                full_chapter_text = get_full_text(pdf_path, cache_path)
                                topics_data = extract_topics_from_pdf(pdf_path)

                                cur.execute(
                                    "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                    (subject_id, chapter_number_counter, chapter_name, full_chapter_text),
                                )
                                chapter_id = cur.fetchone()[0]
                                chapter_number_counter += 1

                                if topics_data:
                                    topic_values = [(chapter_id, topic['topic_number'], topic['topic_name']) for topic in topics_data]
                                    psycopg2.extras.execute_values(cur, "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s", topic_values)
                                        
            print("\n✅ All data has been successfully inserted and committed.")

    except FileNotFoundError:
        print(f"❌ Error: The root folder '{pdf_root_full_path}' was not found. Please check the path.")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print("  The transaction has been rolled back.")
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
