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

        # Extract class_number
        class_value = row.get('class', '')
        try:
            class_num = int(class_value.split()[-1])
        except (ValueError, AttributeError, TypeError):
            log(f"[WARN] Skipping chapter {row['chapter_file']}: Invalid class '{class_value}'")
            continue

        # Extract chapter_number (default to 0 if invalid)
        chapter_num_value = row.get('chapter_number', '')
        try:
            chapter_num = int(chapter_num_value)
        except (ValueError, TypeError):
            chapter_num = 0  # Default; adjust if needed
            log(f"[WARN] Defaulting chapter_number to 0 for {row['chapter_file']}: Invalid value '{chapter_num_value}'")

        cursor.execute(
            "INSERT INTO chapters (name, class_number, subject_id, chapter_number) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (row['chapter_file'].replace('.pdf', ''), class_num, subj_id, chapter_num)
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
        topic_name = row.get('heading_text', '') or ''  # Use heading_text as name; default empty if missing
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number, name, full_text) VALUES (%s, %s, %s, %s) ON CONFLICT (chapter_id, topic_number) DO NOTHING",
            (chap_id, row['heading_number'], topic_name, '')  # Add 'name' from heading_text, full_text empty
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

    # Step 2: Unique chapters
    chapters_df = df.drop_duplicates(subset=['chapter_file'])[['subject', 'class', 'chapter_file', 'chapter_number']]
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
