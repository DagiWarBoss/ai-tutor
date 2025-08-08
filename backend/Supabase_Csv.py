import os
import csv
import psycopg2
from dotenv import load_dotenv
import re
import fitz  # PyMuPDF, for full text extraction

# --- Configuration ---
CSV_FILE = "extracted_headings_all_subjects.csv" 
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# ==============================================================================
# --- This is the function to extract all text from a PDF ---
# ==============================================================================
def extract_full_text_from_pdf(pdf_path):
    """
    Opens a PDF file and extracts its entire text content page by page.
    """
    print(f"    - Extracting full text from: {os.path.basename(pdf_path)}")
    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)
        full_text = ""
        # Loop through each page in the document
        for page in doc:
            # Get the text from the current page and append it
            full_text += page.get_text() + "\n"
        # Close the document to free up resources
        doc.close()
        return full_text
    except Exception as e:
        print(f"    [WARNING] Could not extract text from {os.path.basename(pdf_path)}: {e}")
        return "" # Return an empty string if the extraction fails
# ==============================================================================

def create_database_tables(cursor):
    """Creates the new, cleaned-up database schema."""
    cursor.execute("CREATE TABLE IF NOT EXISTS subjects (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL)")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            class_number TEXT NOT NULL,
            chapter_number TEXT NOT NULL,
            subject_id INTEGER REFERENCES subjects(id),
            full_text TEXT -- The column for the chapter's full content
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            topic_number TEXT NOT NULL,
            name TEXT NOT NULL,
            chapter_id INTEGER REFERENCES chapters(id)
        )
    ''')
    print("[INFO] Database tables created with the final schema.")

def get_or_create_id(cursor, table, name_column, name_value, other_cols={}):
    """Helper function to get an ID if it exists, or create the row and get the new ID."""
    select_query = f'SELECT id FROM {table} WHERE "{name_column}" = %s'
    params = (name_value,)
    for col, val in other_cols.items():
        select_query += f' AND "{col}" = %s'
        params += (val,)
    cursor.execute(select_query, params)
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        all_cols = {name_column: name_value, **other_cols}
        columns_str = ', '.join(f'"{k}"' for k in all_cols.keys())
        placeholders_str = ', '.join(['%s'] * len(all_cols))
        insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders_str}) RETURNING id"
        cursor.execute(insert_query, tuple(all_cols.values()))
        return cursor.fetchone()[0]

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file.")
        return
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase database: {e}")
        return
    
    create_database_tables(cursor)
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            chapters_processed = {}
            
            print(f"[INFO] Reading data from {CSV_FILE} to populate database...")
            for row in reader:
                subject_name = row['subject']
                class_name = row['class']
                source_file = row['chapter_file']
                chapter_number = row['chapter_number']
                topic_number = row['heading_number']
                topic_name = row['heading_text']
                
                chapter_name_from_file = os.path.splitext(source_file)[0]
                
                if chapter_name_from_file not in chapters_processed:
                    print(f"  - Processing new chapter: {chapter_name_from_file}")
                    
                    pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_name, source_file)
                    
                    # Call the function to get the chapter's full text
                    full_chapter_text = extract_full_text_from_pdf(pdf_path)
                    
                    subject_id = get_or_create_id(cursor, 'subjects', 'name', subject_name)
                    chapter_id = get_or_create_id(cursor, 'chapters', 'name', chapter_name_from_file, 
                                                  {
                                                      'class_number': class_name, 
                                                      'chapter_number': chapter_number,
                                                      'subject_id': subject_id,
                                                      'full_text': full_chapter_text
                                                  })
                    chapters_processed[chapter_name_from_file] = chapter_id
                else:
                    chapter_id = chapters_processed[chapter_name_from_file]
                
                cursor.execute(
                    "INSERT INTO topics (topic_number, name, chapter_id) VALUES (%s, %s, %s)",
                    (topic_number, topic_name, chapter_id)
                )

    except FileNotFoundError:
        print(f"[ERROR] The file '{CSV_FILE}' was not found.")
        conn.close()
        return
    except KeyError as e:
        print(f"[ERROR] A column name in your CSV does not match the script. Missing key: {e}")
        conn.close()
        return
        
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n[SUCCESS] All data has been successfully imported into your Supabase project with the new schema.")

if __name__ == '__main__':
    main()