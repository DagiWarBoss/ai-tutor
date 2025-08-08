import os
import psycopg2
from dotenv import load_dotenv

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def main():
    # --- Step 1: Get a list of all actual PDF files on your computer ---
    local_chapter_names = set()
    print("[INFO] Scanning your local PDF files...")
    for root, dirs, files in os.walk(PDF_ROOT_FOLDER):
        for filename in files:
            if filename.lower().endswith(".pdf"):
                # Store the name without the ".pdf" extension
                local_chapter_names.add(os.path.splitext(filename)[0])
    
    print(f"[INFO] Found {len(local_chapter_names)} chapters on your hard drive.")

    # --- Step 2: Connect to the database and get the list of chapters it has ---
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    cursor.execute("SELECT id, name FROM chapters")
    db_chapters = cursor.fetchall()
    db_chapter_map = {name: chapter_id for chapter_id, name in db_chapters}
    
    print(f"[INFO] Found {len(db_chapter_map)} chapters in the database.")

    # --- Step 3: Find which chapters are in the DB but NOT on your computer ---
    chapters_to_delete = set(db_chapter_map.keys()) - local_chapter_names
    
    if not chapters_to_delete:
        print("\n[SUCCESS] Your database is already in sync with your local files. Nothing to delete.")
        conn.close()
        return

    print(f"\n[INFO] Found {len(chapters_to_delete)} stale chapters to delete:")
    for name in sorted(list(chapters_to_delete)):
        print(f"  - {name}")

    # --- Step 4: Delete the old chapters and their topics ---
    print("\n[INFO] Starting deletion process...")
    for chapter_name in chapters_to_delete:
        chapter_id_to_delete = db_chapter_map[chapter_name]
        
        # First, delete topics linked to this chapter to avoid foreign key errors
        print(f"  - Deleting topics for chapter ID: {chapter_id_to_delete} ('{chapter_name}')...")
        cursor.execute("DELETE FROM topics WHERE chapter_id = %s", (chapter_id_to_delete,))
        
        # Then, delete the chapter itself
        print(f"  - Deleting chapter: '{chapter_name}'...")
        cursor.execute("DELETE FROM chapters WHERE id = %s", (chapter_id_to_delete,))

    # --- Step 5: Commit changes and close connection ---
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n[SUCCESS] Database has been cleaned and is now in sync with your local PDF files.")

if __name__ == '__main__':
    main()