import os
import psycopg2
import psycopg2.extras
import json
from dotenv import load_dotenv
from together import Together
import time

# --- Explicitly load the .env file from the backend directory ---
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
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"    - ERROR: Could not connect to database: {e}")
        return None

def get_topics_from_ai(chapter_text, chapter_name):
    """Uses an LLM to generate a structured list of topics from chapter text."""
    max_chars = 20000 
    if len(chapter_text) > max_chars:
        chapter_text = chapter_text[:max_chars]

    try:
        system_message = (
            "You are an expert data analyst specializing in the NCERT curriculum. "
            "Your task is to thoroughly read the provided textbook chapter text and extract a structured list of all its main topics and sub-topics. "
            "Pay close attention to headings, numbered lists, bolded text, and key concepts. Be comprehensive. "
            "Your entire response MUST be a single, valid JSON object containing a single key 'topics'. "
            "The value of 'topics' should be an array of objects, where each object has two keys: 'topic_number' (as a string, e.g., '13.4.1') and 'topic_name' (as a string, e.g., 'Radioactivity'). "
            "Do not invent topics; only extract them from the provided text."
        )
        
        user_message_content = (
            f"Please extract the topics from the following chapter titled '{chapter_name}':\n\n"
            f"--- TEXTBOOK CHAPTER START ---\n"
            f"{chapter_text}\n"
            f"--- TEXTBOOK CHAPTER END ---"
        )
        
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages,
            max_tokens=3000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        
        response_content = response.choices[0].message.content.strip()
        parsed_json = json.loads(response_content)
        return parsed_json.get("topics", [])

    except json.JSONDecodeError:
        print("    - ERROR: AI returned invalid JSON. Skipping chapter.")
        return None
    except Exception as e:
        print(f"    - ERROR: An unexpected error occurred with the AI model: {e}")
        return None

def main():
    """Fetches chapters, uses AI to generate clean topics, and updates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Ensure .env file is correct.")
        return

    all_chapters = []
    # Step 1: Get the list of all chapters first
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                print("Fetching all chapters from the database...")
                # We only fetch chapters that have no topics yet, making it re-runnable
                cur.execute("""
                    SELECT c.id, c.name, c.full_text 
                    FROM chapters c 
                    LEFT JOIN topics t ON c.id = t.chapter_id 
                    WHERE t.id IS NULL
                """)
                all_chapters = cur.fetchall()
                print(f"Found {len(all_chapters)} chapters that need topics refined.")
        except psycopg2.Error as e:
            print(f"❌ Database error during fetch: {e}")
        finally:
            conn.close()
    
    if not all_chapters:
        print("✅ All chapters seem to have topics already. If you want to re-run for all, please clean the 'topics' table in Supabase first.")
        return

    # Step 2: Process each chapter individually
    for i, (chapter_id, chapter_name, full_text) in enumerate(all_chapters):
        print(f"\nProcessing chapter {i+1}/{len(all_chapters)}: '{chapter_name}' (ID: {chapter_id})")
        
        if not full_text or not full_text.strip():
            print("    - Warning: Chapter has no text. Skipping.")
            continue

        ai_generated_topics = get_topics_from_ai(full_text, chapter_name)

        if ai_generated_topics:
            # Step 3: Open a new connection just for this update
            update_conn = get_db_connection()
            if update_conn:
                try:
                    with update_conn.cursor() as update_cur:
                        topic_values = [
                            (chapter_id, topic.get('topic_number', ''), topic.get('topic_name', ''))
                            for topic in ai_generated_topics
                        ]
                        
                        psycopg2.extras.execute_values(
                            update_cur,
                            "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s",
                            topic_values
                        )
                        print(f"    - Success: Inserted {len(topic_values)} new AI-generated topics.")
                    update_conn.commit() # Commit the changes for this chapter
                except psycopg2.Error as e:
                    print(f"    - ERROR: Database update failed for this chapter: {e}")
                    update_conn.rollback()
                finally:
                    update_conn.close()
        
        time.sleep(2) # To avoid hitting API rate limits

    print("\n✅ All chapters have been processed and topics have been refined.")
    print("\nScript finished.")

if __name__ == '__main__':
    main()
