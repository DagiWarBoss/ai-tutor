import os
import psycopg2
import psycopg2.extras
import json
from dotenv import load_dotenv
from together import Together
import time

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

def get_structured_topics_from_ai(chapter_text, chapter_name):
    """Uses an LLM to generate a structured list of primary (numbered) and secondary (unnumbered) topics."""
    max_chars = 25000 
    if len(chapter_text) > max_chars:
        chapter_text = chapter_text[:max_chars]

    try:
        system_message = (
            "You are an expert data analyst specializing in the NCERT curriculum. Your task is to read the provided textbook chapter and extract a structured list of all its topics and headings. You must differentiate between official, numbered topics and other important, unnumbered headings."
            "Your entire response MUST be a single, valid JSON object with two keys: 'numbered_topics' and 'other_headings'."
            "The value for each key should be an array of objects, where each object has 'topic_number' and 'topic_name'."
            "For 'other_headings', the 'topic_number' can be an empty string."
        )
        user_message_content = f"Please extract the topics and headings from the following chapter titled '{chapter_name}':\n\n--- TEXTBOOK CHAPTER START ---\n{chapter_text}\n--- TEXTBOOK CHAPTER END ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages,
            max_tokens=3000,
            temperature=0.05,
            response_format={"type": "json_object"},
        )
        
        response_content = response.choices[0].message.content.strip()
        return json.loads(response_content)

    except Exception as e:
        print(f"    - ERROR: An unexpected error occurred with the AI model: {e}")
        return None

def main():
    """Fetches chapters, uses AI to generate structured topics, and updates the database."""
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

        structured_topics = get_structured_topics_from_ai(full_text, chapter_name)

        if structured_topics:
            update_conn = get_db_connection()
            if update_conn:
                try:
                    with update_conn.cursor() as update_cur:
                        update_cur.execute("DELETE FROM topics WHERE chapter_id = %s", (chapter_id,))
                        print(f"    - Deleted {update_cur.rowcount} old topics.")

                        topics_to_insert = []
                        
                        numbered_topics = structured_topics.get('numbered_topics', [])
                        for topic in numbered_topics:
                            topics_to_insert.append((chapter_id, topic.get('topic_number', ''), topic.get('topic_name', ''), True)) # is_primary_topic = TRUE

                        other_headings = structured_topics.get('other_headings', [])
                        for heading in other_headings:
                            topics_to_insert.append((chapter_id, heading.get('topic_number', ''), heading.get('topic_name', ''), False)) # is_primary_topic = FALSE

                        if topics_to_insert:
                            psycopg2.extras.execute_values(
                                update_cur,
                                "INSERT INTO topics (chapter_id, topic_number, name, is_primary_topic) VALUES %s",
                                topics_to_insert
                            )
                            print(f"    - Success: Inserted {len(topics_to_insert)} new AI-generated topics/headings.")
                    update_conn.commit()
                except psycopg2.Error as e:
                    print(f"    - ERROR: Database update failed for this chapter: {e}")
                    update_conn.rollback()
                finally:
                    update_conn.close()
        
        time.sleep(2)

    print("\n✅ All chapters have been processed and topics have been refined.")
    print("\nScript finished.")

if __name__ == '__main__':
    main()
