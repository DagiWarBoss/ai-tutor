import os
import psycopg2
from dotenv import load_dotenv
from together import Together
import time


# --- Configuration ---
# This script will read your .env file for the single connection string and API key
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")


MODEL_NAME = "BAAI/bge-large-en-v1.5"


def log(msg: str):
    print(msg, flush=True)


def main():
    if not SUPABASE_URI:
        log("❌ Error: SUPABASE_CONNECTION_STRING not found in .env file.")
        return
    if not TOGETHER_API_KEY:
        log("❌ Error: TOGETHER_API_KEY not found in .env file.")
        return


    log(f"Connecting to Together API with model: {MODEL_NAME} ...")
    client = Together(api_key=TOGETHER_API_KEY)


    conn = None
    try:
        with psycopg2.connect(SUPABASE_URI) as conn:
            log("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                # Fetch all TOPICS that have full_text
                cur.execute("SELECT id, full_text FROM topics WHERE full_text IS NOT NULL")
                topics = cur.fetchall()


                log(f"Found {len(topics)} topics to embed. Starting process...")


                for i, (topic_id, full_text) in enumerate(topics):
                    log(f"  -> Processing topic {i+1}/{len(topics)} (ID: {topic_id})...")


                    if not full_text or not full_text.strip():
                        log(f"     - Warning: Topic {topic_id} has no text. Skipping.")
                        continue


                    try:
                        # Call Together API for embedding
                        embed_response = client.embeddings.create(
                            input=[full_text],
                            model=MODEL_NAME
                        )
                        embedding = embed_response.data[0].embedding


                        # Update the database with the new embedding (768 length vector)
                        cur.execute(
                            "UPDATE topics SET embedding = %s WHERE id = %s",
                            (embedding, topic_id)
                        )
                        # Optional: commit every N updates if desired
                        if i % 20 == 0:
                            conn.commit()
                        # Sleep briefly to avoid hitting API rate limits
                        time.sleep(0.2)


                    except Exception as e:
                        log(f"ERROR: Failed to generate embedding for topic {topic_id}: {e}")


            conn.commit()
            log("\n✅ All topic embeddings have been generated and saved.")


    except psycopg2.Error as e:
        log(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        log("   The transaction has been rolled back.")
    except Exception as e:
        log(f"❌ An unexpected error occurred: {e}")
    finally:
        log("\nScript finished.")


if __name__ == '__main__':
    main()
