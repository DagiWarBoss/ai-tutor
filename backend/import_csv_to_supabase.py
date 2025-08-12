import os
import psycopg2
from dotenv import load_dotenv
import pandas as pd

# Paths (update if needed)
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\gemini_csv.csv"

# Load environment
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def log(msg: str):
    print(msg, flush=True)

def connect_db():
    conn = psycopg2.connect(SUPABASE_URI)
    cursor = conn.cursor()
    return conn, cursor

def insert_subjects(cursor, unique_subjects):
    inserted = {}
    for subj in unique_subjects:
        cursor.execute("INSERT INTO subjects (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id", (subj,))
        row = cursor.fetchone()
        if row:
            inserted[subj] = row[0]
        else:
            cursor.execute("SELECT id FROM subjects WHERE name = %s", (subj,))
            inserted[subj] = cursor.fetchone()[0]
    return inserted

def insert_chapters(cursor, chapters_df, subject_map):
    inserted = {}
    for _, row in chapters_df.iterrows():
        subj_id = subject_map.get(row['subject'])
        if not subj_id:
            log(f"[WARN] Skipping chapter {row['chapter_file']}: No subject ID for {row['subject']}")
            continue
        
        # FIX: Robust extraction of class_num
        class_value = row.get('class')  # Safely get value
        if pd.isna(class_value) or not isinstance(class_value, str) or not class_value.strip():
            log(f"[WARN] Skipping chapter {row['chapter_file']}: Invalid or missing 'class' value ({class_value})")
            continue
        
        try:
            # Extract number (e.g., 'Class 11' -> 11, or '11' -> 11)
            class_num_str = class_value.split()[-1].strip()  # Last word
            class_num = int(class_num_str)
        except (ValueError, IndexError, AttributeError, TypeError) as e:
            log(f"[WARN] Skipping chapter {row['chapter_file']}: Could not extract integer from 'class' value '{class_value}' ({e})")
            continue
        
        cursor.execute(
            "INSERT INTO chapters (name, class_number, subject_id) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (row['chapter_file'].replace('.pdf', ''), class_num, subj_id)
        )
        chap_row = cursor.fetchone()
        if chap_row:
            inserted[row['chapter_file']] = chap_row[0]
        else:
            cursor.execute("SELECT id FROM chapters WHERE name = %s", (row['chapter_file'].replace('.pdf', ''),))
            inserted[row['chapter_file']] = cursor.fetchone()[0]
    return inserted

def insert_topics(cursor, topics_df, chapter_map):
    for _, row in topics_df.iterrows():
        chap_id = chapter_map.get(row['chapter_file'])
        if not chap_id:
            log(f"[WARN] Skipping topic {row['heading_number']}: No chapter ID for {row['chapter_file']}")
            continue
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number, full_text) VALUES (%s, %s, %s) ON CONFLICT (chapter_id, topic_number) DO NOTHING",
            (chap_id, row['heading_number'], '')  # full_text empty; will be updated by OCR script
        )

def main():
    try:
        conn, cursor = connect_db()
        log("[INFO] Connected to Supabase.")
    except Exception as e:
        log(f"[ERROR] Connection failed: {e}")
        return

    try:
        df = pd.read_csv(CSV_PATH, dtype=str).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        log(f"[INFO] Loaded CSV with {len(df)} rows.")
    except Exception as e:
        log(f"[ERROR] CSV load failed: {e}")
        return

    # Step 1: Unique subjects
    unique_subjects = df['subject'].unique()
    subject_map = insert_subjects(cursor, unique_subjects)
    log(f"[INFO] Inserted {len(subject_map)} subjects.")

    # Step 2: Unique chapters (group by chapter_file, take first class/subject)
    chapters_df = df.drop_duplicates(subset=['chapter_file'])[['subject', 'class', 'chapter_file']]
    chapter_map = insert_chapters(cursor, chapters_df, subject_map)
    log(f"[INFO] Inserted {len(chapter_map)} chapters.")

    # Step 3: All topics
    insert_topics(cursor, df, chapter_map)
    log(f"[INFO] Inserted topics from CSV.")

    conn.commit()
    cursor.close()
    conn.close()
    log("[SUCCESS] CSV data imported to Supabase.")

if __name__ == '__main__':
    main()
