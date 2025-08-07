import os
import csv
import psycopg2 # The PostgreSQL driver
from dotenv import load_dotenv
import re

# --- Configuration ---
CSV_FILE = "extracted_headings_all_subjects.csv"
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()

# Get the connection string from your .env file
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def create_database_tables(cursor):
    """Creates the database schema (tables) in Supabase if they don't already exist."""
    # Table for subjects (e.g., Chemistry, Physics)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    # Table for chapters (e.g., Chemical Bonding, Wave Optics)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            class_number INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            subject_id INTEGER REFERENCES subjects(id)
        )
    ''')
    # Table for all the topics and subtopics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            topic_number TEXT NOT NULL,
            name TEXT NOT NULL,
            chapter_id INTEGER REFERENCES chapters(id)
        )
    ''')
    print("[INFO] Database tables created or already exist in Supabase.")

def get_or_create_id(cursor, table, name_column, name_value, other_cols={}):
    """
    Helper function to get an ID if it exists, or create the row and get the new ID.
    This prevents creating duplicate subjects or chapters.
    """
    select_query = f'SELECT id FROM {table} WHERE "{name_column}" = %s'
    params = (name_value,)
    
    for col, val in other_cols.items():
        select_query += f' AND "{col}" = %s'
        params += (val,)
        
    cursor.execute(select_query, params)
    result = cursor.fetchone()
    
    if result:
        return result[0] # Return existing ID
    else:
        all_cols = {name_column: name_value, **other_cols}
        columns_str = ', '.join(f'"{k}"' for k in all_cols.keys())
        placeholders_str = ', '.join(['%s'] * len(all_cols))
        
        insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders_str}) RETURNING id"
        cursor.execute(insert_query, tuple(all_cols.values()))
        return cursor.fetchone()[0] # Return the new ID

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file. Please add it.")
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
            print(f"[INFO] Reading data from {CSV_FILE}...")
            
            for row in reader:
                source_file = row['source_file']
                topic_number = row['topic_number']
                topic_name = row['extracted_name']
                
                # Logic to find Subject and Class from the filename remains the same
                match = re.search(r"[\\/]([^\\/]+)[\\/]Class (\d+)", root + "\\" + source_file, re.IGNORECASE)
                
                if match:
                    subject_name = match.group(1)
                    class_number = int(match.group(2))
                    chapter_name = os.path.splitext(source_file)[0]
                else:
                    print(f"[WARNING] Could not determine Subject/Class for '{source_file}'. Using placeholders.")
                    subject_name = "Unknown Subject"
                    class_number = 0
                    chapter_name = os.path.splitext(source_file)[0]
                
                subject_id = get_or_create_id(cursor, 'subjects', 'name', subject_name)
                chapter_id = get_or_create_id(cursor, 'chapters', 'name', chapter_name, 
                                              {'class_number': class_number, 'subject_id': subject_id, 'source_file': source_file})
                
                cursor.execute(
                    "INSERT INTO topics (topic_number, name, chapter_id) VALUES (%s, %s, %s)",
                    (topic_number, topic_name, chapter_id)
                )

    except FileNotFoundError:
        print(f"[ERROR] The file '{CSV_FILE}' was not found.")
        conn.close()
        return
        
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n[SUCCESS] All data has been successfully imported into your Supabase project.")

if __name__ == '__main__':
    main()