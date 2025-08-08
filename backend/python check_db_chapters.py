import os
import psycopg2
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file.")
        return

    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        print("[INFO] Successfully connected to Supabase database.")
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    # --- This is the only action: Read and print chapter names ---
    print("\n--- Chapters Currently in Supabase Database ---")
    
    try:
        cursor.execute("SELECT name FROM chapters ORDER BY name;")
        all_chapters = cursor.fetchall()
        
        if not all_chapters:
            print("  - The 'chapters' table is empty.")
        else:
            for i, chapter in enumerate(all_chapters):
                print(f"  {i+1}. {chapter[0]}")
        
        print(f"\n-------------------------------------------------")
        print(f"Total chapters found in database: {len(all_chapters)}")
        print(f"-------------------------------------------------")

    except Exception as e:
        print(f"\n[ERROR] Could not query the 'chapters' table: {e}")

    # --- Clean up ---
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()