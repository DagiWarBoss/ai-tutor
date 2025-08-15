import os
import re
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the database connection string from environment variable
DB_CONN = os.getenv("SUPABASE_CONNECTION_STRING")

if not DB_CONN:
    raise ValueError("Missing SUPABASE_CONNECTION_STRING in environment variables")

# Map of chapter IDs to OCR cache file paths (update filenames as per your cache)
OCR_FILES = {
    157: r"ocr_cache\Chemistry_Chapter_8.txt",  # Replace with exact filename
    155: r"ocr_cache\Chemistry_Chapter_5.txt",  # Replace with exact filename
    174: r"ocr_cache\Mathematics_Chapter_14.txt",  # Replace with exact filename
    183: r"ocr_cache\Mathematics_Chapter_5.txt"   # Replace with exact filename
}

# List of (chapter_id, topic_number) to update with extracted text
TOPICS_TO_EXTRACT = [
    ('157', '7.5'), ('157', '7.5.1'), ('157', '7.5.2'), ('157', '7.5.3'),
    ('158', '8.1'), ('158', '8.11'), ('158', '8.12'), ('158', '8.2'),
    ('158', '8.21'), ('158', '8.22'), ('158', '8.3'), ('158', '8.4'),
    ('158', '8.5'), ('158', '8.6'), ('158', '8.61'), ('158', '8.62'),
    ('158', '8.7'), ('158', '8.8'), ('158', '8.9'), ('158', '8.91'), ('158', '8.92'),
    ('155', '2.78'), ('155', '2.79'), ('156', '5.1'), ('156', '5.11'), ('156', '5.12'),
    ('156', '5.13'), ('156', '5.14'), ('156', '5.2'), ('156', '5.21'), ('156', '5.22'),
    ('156', '5.3'), ('156', '5.4'), ('156', '5.41'), ('156', '5.42'), ('156', '5.43'),
    ('156', '5.44'), ('156', '5.45'), ('174', '14.1'), ('174', '14.11'), ('174', '14.12'),
    ('174', '14.13'), ('174', '14.14'), ('174', '14.15'), ('174', '14.2'), ('174', '14.21'),
    ('174', '14.22'), ('174', '14.23'), ('174', '14.24'), ('175', '2.1'), ('175', '2.2'),
    ('175', '2.3'), ('175', '2.4'), ('175', '2.41'), ('175', '2.42'), ('176', '8.1'),
    ('176', '8.2'), ('176', '8.3'), ('176', '8.4'),
    ('183', '5.1'), ('183', '5.2'), ('183', '5.21'), ('183', '5.3'), ('183', '5.31'), ('183', '5.32'),
    ('183', '5.33'), ('183', '5.4'), ('183', '5.5'), ('183', '5.6'), ('183', '5.7'), ('183', '5.8')
]

def extract_topic_text_from_ocr(ocr_path, topic_number):
    """
    Extract text belonging to a specific topic number from OCR file.
    Returns the text from the topic header until next topic header or end of file.
    """
    with open(ocr_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex pattern: topic number at line start, followed by any text (including newlines), non-greedy, 
    # until next topic number or EOF
    pattern = re.compile(
        rf'^\s*{re.escape(topic_number)}\s.*?(?=^\s*\d+(\.\d+)*\s|\Z)', 
        re.DOTALL | re.MULTILINE)
    match = pattern.search(content)
    if match:
        return match.group().strip()
    else:
        return ""

def main():
    import psycopg2

    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    for chapter_id, topic_num in TOPICS_TO_EXTRACT:
        chapter_num = int(chapter_id)
        if chapter_num not in OCR_FILES:
            print(f"No OCR file mapped for chapter {chapter_num}, skipping topic {topic_num}")
            continue

        ocr_file = OCR_FILES[chapter_num]
        if not os.path.exists(ocr_file):
            print(f"OCR file not found: {ocr_file}")
            continue

        extracted_text = extract_topic_text_from_ocr(ocr_file, topic_num)
        if not extracted_text:
            print(f"No text found for topic {topic_num} in chapter {chapter_num}")
            continue

        # Update database; adjust table and column names if needed
        try:
            cur.execute("""
                UPDATE public.topics
                SET full_text = %s
                WHERE chapter_id = %s AND topic_number = %s
            """, (extracted_text, chapter_num, topic_num))
            print(f"Updated topic {topic_num} in chapter {chapter_num}")
        except Exception as e:
            print(f"Failed to update topic {topic_num} in chapter {chapter_num}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done updating topics' full_text.")

if __name__ == "__main__":
    main()
