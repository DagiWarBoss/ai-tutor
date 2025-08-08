import os
import csv
import psycopg2 # The PostgreSQL driver
from dotenv import load_dotenv
import re

# --- Configuration ---
# Make sure your CSV file is named this, or change the name here
CSV_FILE = "extracted_headings_all_subjects.csv" 
DATABASE_FILE = "tutor_database.db"
load_dotenv()

# Get the connection string from your .env file
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def create_database_tables(cursor):
    """Creates the database schema (tables) in Supabase if they don't already exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            class_number TEXT NOT NULL,
            source_file TEXT NOT NULL,
            subject_id INTEGER REFERENCES subjects(id)
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
    print("[INFO] Database tables created or already exist in Supabase.")

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
                # --- FIX: Using the correct column names from your CSV file ---
                subject_name = row['subject']
                class_name = row['class'] # e.g., "Class 11"
                source_file = row['chapter_file']
                topic_number = row['heading_number']
                topic_name = row['heading_text']
                
                # Clean up chapter name from filename
                chapter_name = os.path.splitext(source_file)[0]
                
                # Get or create IDs for subject and chapter to avoid duplicates
                subject_id = get_or_create_id(cursor, 'subjects', 'name', subject_name)
                chapter_id = get_or_create_id(cursor, 'chapters', 'name', chapter_name, 
                                              {'class_number': class_name, 'subject_id': subject_id, 'source_file': source_file})
                
                # Insert the topic into the database
                cursor.execute(
                    "INSERT INTO topics (topic_number, name, chapter_id) VALUES (%s, %s, %s)",
                    (topic_number, topic_name, chapter_id)
                )

    except FileNotFoundError:
        print(f"[ERROR] The file '{CSV_FILE}' was not found. Please make sure its name matches.")
        conn.close()
        return
    except KeyError as e:
        print(f"[ERROR] A column name in your CSV does not match the script. Missing key: {e}")
        print("Please ensure your CSV header row is: subject,class,chapter_file,chapter_number,heading_number,heading_text")
        conn.close()
        return
        
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n[SUCCESS] All data has been successfully imported into your Supabase project.")

if __name__ == '__main__':
    main()