import os
import psycopg2
from dotenv import load_dotenv
import textwrap

# --- Configuration ---
# TODO: SET THE CHAPTER AND TOPIC YOU WANT TO CHECK
TARGET_CHAPTER_ID = 1       # The ID of the chapter from the 'chapters' table in Supabase
TARGET_TOPIC_NUMBER = "1.2"   # The exact topic number you want to verify
# --------------------

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file.")
        return

    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    # Fetch the specific topic from the database
    cursor.execute(
        "SELECT name, full_text FROM topics WHERE chapter_id = %s AND topic_number = %s",
        (TARGET_CHAPTER_ID, TARGET_TOPIC_NUMBER)
    )
    result = cursor.fetchone()
    
    print("\n--- Verification Result ---")
    if result:
        name, full_text = result
        print(f"Chapter ID:   {TARGET_CHAPTER_ID}")
        print(f"Topic Number: {TARGET_TOPIC_NUMBER}")
        print(f"Topic Name:   {name}")
        print("---------------------------------")
        print("Stored Text Content:")
        print("---------------------------------")
        if full_text:
            # textwrap helps format long text for easier reading in the terminal
            print(textwrap.fill(full_text, width=100))
        else:
            print("[NO TEXT STORED FOR THIS TOPIC]")
            
    else:
        print(f"Could not find Topic '{TARGET_TOPIC_NUMBER}' for Chapter ID '{TARGET_CHAPTER_ID}' in the database.")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()