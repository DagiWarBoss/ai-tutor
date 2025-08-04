import os
import psycopg2
import psycopg2.extras
import json
from dotenv import load_dotenv
from together import Together
import time
import re

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Securely load API Keys & DB Credentials ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- Initialize Together AI Client ---
llm_client = Together(api_key=TOGETHER_API_KEY)

def get_db_connection():
    """Establishes and returns a new database connection."""
    try:
        return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
    except psycopg2.Error as e:
        print(f"    - ERROR: Could not connect to database: {e}")
        return None

def get_topics_from_chunk(text_chunk):
    """Uses an LLM on a small chunk of text to find topics."""
    try:
        system_message = (
            "You are a data extraction expert. Your task is to read the provided text chunk and extract a list of all official, numbered topics and sub-topics. "
            "You MUST ONLY extract headings that are preceded by a number (e.g., '7.1', '7.1.1'). Ignore all other text. "
            "Your entire response MUST be a single, valid JSON object with a single key 'topics', which is an array of objects. "
            "Each object must have 'topic_number' and 'topic_name'. If no topics are found, return an empty array."
        )
        user_message_content = f"Please extract the numbered topics from the following text chunk:\n\n--- TEXT CHUNK START ---\n{text_chunk}\n--- TEXT CHUNK END ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages,
            max_tokens=1024,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        
        response_content = response.choices[0].message.content.strip()
        return json.loads(response_content).get('topics', [])
    except Exception as e:
        print(f"    - ERROR: AI call failed for chunk: {e}")
        return []

def main():
    """Fetches chapters, processes them in chunks, and updates the database."""
    all_chapters = []
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                print("Fetching all chapters from the database...")
                cur.execute("SELECT id, name, full_text FROM chapters")
                all_chapters = cur.fetchall()
                print(f"Found {len(all_chapters)} chapters to process.")
        finally:
            conn.close()
    
    if not all_chapters:
        print("No chapters found to process.")
        return

    for i, (chapter_id, chapter_name, full_text) in enumerate(all_chapters):
        print(f"\nProcessing chapter {i+1}/{len(all_chapters)}: '{chapter_name}' (ID: {chapter_id})")
        
        if not full_text or not full_text.strip():
            print("    - Warning: Chapter has no text. Skipping.")
            continue

        # --- CHUNKING LOGIC ---
        chunk_size = 4000  # Characters per chunk
        overlap = 500      # Characters of overlap to avoid cutting off topics
        text_chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size - overlap)]
        
        print(f"    - Split chapter into {len(text_chunks)} chunks.")
        all_found_topics = []

        for j, chunk in enumerate(text_chunks):
            print(f"      - Processing chunk {j+1}/{len(text_chunks)}...")
            topics_in_chunk = get_topics_from_chunk(chunk)
            if topics_in_chunk:
                all_found_topics.extend(topics_in_chunk)
            time.sleep(2) # Rate limit

        # --- DEDUPLICATION AND SAVING ---
        if all_found_topics:
            seen_topics = set()
            unique_topics = []
            for topic in all_found_topics:
                topic_tuple = (topic.get('topic_number'), topic.get('topic_name'))
                if topic_tuple not in seen_topics:
                    seen_topics.add(topic_tuple)
                    unique_topics.append(topic)
            
            update_conn = get_db_connection()
            if update_conn:
                try:
                    with update_conn.cursor() as update_cur:
                        update_cur.execute("DELETE FROM topics WHERE chapter_id = %s", (chapter_id,))
                        
                        topics_to_insert = [
                            (chapter_id, t.get('topic_number'), t.get('topic_name'), True)
                            for t in unique_topics if t.get('topic_number')
                        ]

                        if topics_to_insert:
                            psycopg2.extras.execute_values(
                                update_cur,
                                "INSERT INTO topics (chapter_id, topic_number, name, is_primary_topic) VALUES %s",
                                topics_to_insert
                            )
                            print(f"    - Success: Inserted {len(topics_to_insert)} unique AI-generated topics.")
                        else:
                             print("    - Warning: No valid numbered topics found after processing all chunks.")
                    update_conn.commit()
                except psycopg2.Error as e:
                    print(f"    - ERROR: Database update failed: {e}")
                    update_conn.rollback()
                finally:
                    update_conn.close()
        else:
            print("    - Warning: No topics found in any chunk for this chapter.")

    print("\n✅ All chapters have been processed and topics have been refined.")
    print("\nScript finished.")

if __name__ == '__main__':
    main()
