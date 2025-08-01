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

def get_topics_from_ai(chapter_text, chapter_name):
    """Uses an LLM to generate a structured list of topics from chapter text."""
    # Truncate text to stay within model limits
    max_chars = 20000 
    if len(chapter_text) > max_chars:
        chapter_text = chapter_text[:max_chars]

    try:
        system_message = (
            "You are an expert data analyst specializing in the NCERT curriculum. "
            "Your task is to read the provided textbook chapter text and extract a structured list of its main topics and sub-topics. "
            "Analyze the text for headings, numbered lists, and key concepts. "
            "Your entire response MUST be a single, valid JSON object containing a single key 'topics'. "
            "The value of 'topics' should be an array of objects, where each object has two keys: 'topic_number' (as a string) and 'topic_name' (as a string). "
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
            max_tokens=2048,
            temperature=0.1, # Low temperature for factual, deterministic output
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

    try:
        with psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        ) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, full_text FROM chapters")
                all_chapters = cur.fetchall()

                for i, (chapter_id, chapter_name, full_text) in enumerate(all_chapters):
                    print(f"\nProcessing chapter {i+1}/{len(all_chapters)}: '{chapter_name}' (ID: {chapter_id})")
                    
                    if not full_text or not full_text.strip():
                        print("    - Warning: Chapter has no text. Skipping.")
                        continue

                    # Get the structured topics from the AI
                    ai_generated_topics = get_topics_from_ai(full_text, chapter_name)

                    if ai_generated_topics:
                        # First, delete all old, incorrect topics for this chapter
                        cur.execute("DELETE FROM topics WHERE chapter_id = %s", (chapter_id,))
                        print(f"    - Deleted {cur.rowcount} old topics.")

                        # Now, insert the new, clean topics
                        topic_values = [
                            (chapter_id, topic.get('topic_number', ''), topic.get('topic_name', ''))
                            for topic in ai_generated_topics
                        ]
                        
                        psycopg2.extras.execute_values(
                            cur,
                            "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s",
                            topic_values
                        )
                        print(f"    - Success: Inserted {len(topic_values)} new AI-generated topics.")
                    
                    # Add a small delay to avoid hitting API rate limits
                    time.sleep(2) 

            # The 'with' block commits the transaction here
            print("\n✅ All chapters have been processed and topics have been refined.")

    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
