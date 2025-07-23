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

def extract_chapter_number_from_pdf(doc):
    """Scans the first page of a PDF for a 'Unit X' or 'Chapter X' pattern."""
    try:
        first_page_text = doc[0].get_text()
        # Look for patterns like "Unit 7" or "CHAPTER 12"
        match = re.search(r"(?:Unit|CHAPTER)\s*(\d+)", first_page_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception:
        return None
    return None

def extract_topics_from_pdf(doc):
    """
    Smarter topic extraction. Manually scans the first few pages for topic-like text patterns.
    """
    try:
        topics = []
        # A stricter regex: must start a line, have a number, and be followed by capitalized text.
        topic_pattern = re.compile(r"^\s*(\d+\.\d+[\.\d+]*)\s+([A-Z][A-Za-z\s,]+)", re.MULTILINE)
        
        for page_num in range(min(5, doc.page_count)):
            page_text = doc[page_num].get_text()
            matches = topic_pattern.findall(page_text)
            for match in matches:
                topic_number = match[0]
                topic_name = match[1].strip()
                if topic_name and len(topic_name) > 5: # Filter out short junk titles
                    topics.append({"topic_number": topic_number, "topic_name": topic_name})

        if not topics:
             print(f"    - Warning: Could not find topics by scanning text.")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_topics = []
        for topic in topics:
            # Use a tuple for the dictionary to make it hashable for the set
            topic_tuple = tuple(topic.items())
            if topic_tuple not in seen:
                seen.add(topic_tuple)
                unique_topics.append(topic)
        
        return unique_topics

    except Exception as e:
        print(f"    - Error processing TOC for {os.path.basename(doc.name)}: {e}")
        return []

def get_full_text(doc, cache_path):
    """
    Gets full text. Prioritizes reading from a cached .txt file.
    If not found, extracts from PDF and creates a .txt file for next time.
    """
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    print(f"    - Cache miss. Extracting text from PDF...")
    try:
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + " "
        
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"    - Saved text to cache: '{os.path.basename(cache_path)}'")
        
        return full_text.strip()
    except Exception as e:
        print(f"    - Error extracting full text from {os.path.basename(doc.name)}: {e}")
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
                for subject_name in sorted(os.listdir(pdf_root_full_path)):
                    subject_path = os.path.join(pdf_root_full_path, subject_name)
                    if os.path.isdir(subject_path):
                        print(f"\n===== Processing Subject: '{subject_name}' =====")

                        upsert_subject_query = """
                            WITH ins AS (INSERT INTO subjects (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id)
                            SELECT id FROM ins UNION ALL SELECT id FROM subjects WHERE name = %s LIMIT 1;
                        """
                        cur.execute(upsert_subject_query, (subject_name, subject_name))
                        subject_id = cur.fetchone()[0]
                        print(f"  -> Subject '{subject_name}' has ID: {subject_id}")

                        fallback_counter = 1
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
                                
                                try:
                                    doc = fitz.open(pdf_path)
                                    
                                    # Get the real chapter number
                                    chapter_number = extract_chapter_number_from_pdf(doc)
                                    if chapter_number is None:
                                        print(f"    - Warning: Could not find real chapter number. Using fallback counter: {fallback_counter}")
                                        chapter_number = fallback_counter
                                    else:
                                        print(f"    - Success: Found real chapter number: {chapter_number}")

                                    full_chapter_text = get_full_text(doc, cache_path)
                                    topics_data = extract_topics_from_pdf(doc)
                                    
                                    doc.close() # Close the document after processing

                                    cur.execute(
                                        "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                        (subject_id, chapter_number, chapter_name, full_chapter_text),
                                    )
                                    chapter_id = cur.fetchone()[0]
                                    fallback_counter += 1

                                    if topics_data:
                                        print(f"    - Success: Extracted {len(topics_data)} topics. Inserting...")
                                        topic_values = [(chapter_id, topic['topic_number'], topic['topic_name']) for topic in topics_data]
                                        psycopg2.extras.execute_values(cur, "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s", topic_values)
                                
                                except Exception as e:
                                    print(f"  ❌ CRITICAL ERROR processing file {filename}: {e}")
                                        
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
