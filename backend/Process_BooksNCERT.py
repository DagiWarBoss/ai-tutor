### **Step 1: Install Required Libraries**

If you haven't already, open your terminal and install the libraries for handling PDFs and connecting to the database:
```bash
pip install PyMuPDF
pip install psycopg2-binary
```

### **Step 2: Organize Your Files**

Your current file structure is perfect. Just make sure the main folder containing the subject folders (`Chemistry`, `Maths`, `Physics`) is correctly identified in the script.

### **Step 3: The Python Script**

Create a new Python file named `extract_and_populate.py`. Copy the code below into this file. Make sure to **update the placeholder credentials** and the `PDF_ROOT_FOLDER` path.

**File: `extract_and_populate.py`**
```python
import os
import fitz  # PyMuPDF
import psycopg2
import re

# --- YOUR SUPABASE CREDENTIALS ---
# Replace these with your actual database details from Supabase
DB_HOST = "your-supabase-host"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "your-database-password"
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
            # We treat every item in the TOC as a topic for this chapter
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
    conn_string = f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASSWORD}' port='{DB_PORT}'"
    
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        print("✅ Successfully connected to the database.")

        # Walk through the directory structure
        for subject_name in os.listdir(PDF_ROOT_FOLDER):
            subject_path = os.path.join(PDF_ROOT_FOLDER, subject_name)
            if os.path.isdir(subject_path):
                print(f"\nProcessing Subject: {subject_name} (Class {CLASS_LEVEL})")
                
                # Insert Subject and get its ID, or get it if it already exists
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

                # Process each chapter PDF in the subject folder
                chapter_number_counter = 1
                for filename in sorted(os.listdir(subject_path)):
                    if filename.endswith(".pdf"):
                        chapter_name = filename.replace('.pdf', '')
                        print(f"  -> Processing Chapter: {chapter_name}")
                        
                        pdf_path = os.path.join(subject_path, filename)
                        topics_data = extract_topics_from_pdf(pdf_path)
                        
                        # Insert Chapter and get its ID
                        cur.execute(
                            "INSERT INTO chapters (subject_id, chapter_number, name) VALUES (%s, %s, %s) RETURNING id",
                            (subject_id, chapter_number_counter, chapter_name)
                        )
                        chapter_id = cur.fetchone()[0]
                        chapter_number_counter += 1

                        # Insert all topics for this chapter
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
        print(f"❌ Database error: {e}")
    finally:
        if 'cur' in locals() and cur:
            cur.close()
        if 'conn' in locals() and conn:
            conn.close()
        print("Database connection closed.")


if __name__ == '__main__':
    main()
```