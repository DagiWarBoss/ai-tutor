import os
import psycopg2
import re

# REQUIRED: Your Supabase/Postgres connection string
DB_CONN = "YOUR_SUPABASE_POSTGRES_URL"  # fill from your .env or dashboard

# Map chapter numbers to OCR cache files (must match your actual filenames)
OCR_FILES = {
    157: r"ocr_cache\Chemistry_Ch8.txt",     # Chemistry chapter 8
    155: r"ocr_cache\Chemistry_Ch5.txt",     # Chemistry chapter 5
    174: r"ocr_cache\Maths_Ch14.txt",        # Maths chapter 14
    183: r"ocr_cache\Maths_Ch5.txt",         # Maths chapter 5
}

# List of topics you want extracted (as in your screenshots)
TOPICS_TO_EXTRACT = [
    # For chapter 8 (Chemistry)
    ("157", "7.5"), ("157", "7.5.1"), ("157", "7.5.2"), ("157", "7.5.3"),
    ("158", "8.1"), ("158", "8.1.1"), ("158", "8.1.2"), # ...fill rest as needed

    # For chapter 5 (Chemistry)
    ("155", "2.7.8"), ("155", "2.7.9"), ("156", "5.1"), # ...fill rest as needed

    # For chapter 14 (Maths)
    ("174", "14.1"), ("174", "14.1.1"), # ...fill rest as needed

    # For chapter 5 (Maths)
    ("183", "5.1"), ("183", "5.2"), ("183", "5.2.1"), ("183", "5.3"), # ...fill rest as needed
]

def extract_topic_text_from_ocr(ocr_path, topic_name):
    """Extract a topic's text from the OCR cache file using a header match."""
    with open(ocr_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        rf"\b{re.escape(topic_name)}\b.*?(?=\n\d+\.\d+|\Z)", re.DOTALL
    )  # matches the topic heading and grabs everything until the next topic or EOF
    match = pattern.search(content)
    if match:
        return match.group().strip()
    else:
        return ""

def main():
    # Connect to DB
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    for chapter_id, topic_number in TOPICS_TO_EXTRACT:
        ocr_path = OCR_FILES.get(int(chapter_id))
        if not ocr_path or not os.path.exists(ocr_path):
            print(f"OCR file not found for chapter {chapter_id}, skipping: {ocr_path}")
            continue

        topic_text = extract_topic_text_from_ocr(ocr_path, topic_number)
        if not topic_text:
            print(f"No text found for topic {topic_number} in chapter {chapter_id}")
            continue

        # Update the topic's full_text field in DB (adjust for your table/fields!)
        cur.execute("""
            UPDATE public.topics
            SET full_text = %s
            WHERE chapter_id = %s AND topic_number = %s
        """, (topic_text, chapter_id, topic_number))

        print(f"Updated topic {topic_number} in chapter {chapter_id}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
