import os
import psycopg2
from dotenv import load_dotenv
import textwrap

# --- Configuration ---
# TODO: Change this to the name of any chapter you want to check
CHAPTER_NAME_TO_CHECK = "Chemical Bonding And Molecular Structure"
# --------------------

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def log(msg: str):
    print(msg, flush=True)

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        log(f"[ERROR] Could not connect to Supabase: {e}")
        return

    # Find the chapter ID
    cursor.execute("SELECT id FROM chapters WHERE name = %s", (CHAPTER_NAME_TO_CHECK,))
    result = cursor.fetchone()
    if not result:
        log(f"[ERROR] Could not find chapter: '{CHAPTER_NAME_TO_CHECK}' in the database.")
        return
    chapter_id = result[0]

    log(f"\n--- Verifying Data for: {CHAPTER_NAME_TO_CHECK} (Chapter ID: {chapter_id}) ---")

    # --- Verify Topics ---
    log("\n## Checking 3 Random Topics... ##")
    cursor.execute(
        "SELECT topic_number, name, full_text FROM topics WHERE chapter_id = %s AND full_text IS NOT NULL ORDER BY RANDOM() LIMIT 3",
        (chapter_id,)
    )
    topics = cursor.fetchall()
    if topics:
        for num, name, text in topics:
            log(f"\n[TOPIC] {num} - {name}")
            log("-" * 30)
            log(textwrap.fill(text[:500] + "..." if len(text) > 500 else text, width=100))
    else:
        log("[INFO] No topics with text found for this chapter.")

    # --- Verify Questions ---
    log("\n## Checking 3 Random Questions... ##")
    cursor.execute(
        "SELECT question_number, question_text FROM question_bank WHERE chapter_id = %s ORDER BY RANDOM() LIMIT 3",
        (chapter_id,)
    )
    questions = cursor.fetchall()
    if questions:
        for num, text in questions:
            log(f"\n[QUESTION] {num}")
            log("-" * 30)
            log(textwrap.fill(text, width=100))
    else:
        log("[INFO] No questions found for this chapter.")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()