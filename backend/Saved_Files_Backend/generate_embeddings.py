import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np

# --- Configuration ---
# This script will read your .env file for the single connection string
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# This is the model specified in your project plan
MODEL_NAME = 'all-MiniLM-L6-v2'

def log(msg: str):
    print(msg, flush=True)

def main():
    """
    Connects to the database, generates embeddings for TOPICS that don't have them,
    and saves them back to the database.
    """
    if not SUPABASE_URI:
        log("❌ Error: SUPABASE_CONNECTION_STRING not found in .env file.")
        return

    log(f"Loading sentence transformer model: {MODEL_NAME}...")
    # This will download the model from the internet the first time it's run.
    model = SentenceTransformer(MODEL_NAME)
    log("✅ Model loaded successfully.")

    conn = None
    try:
        with psycopg2.connect(SUPABASE_URI) as conn:
            log("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                # --- THIS IS THE KEY CHANGE ---
                # Fetch all TOPICS that have full_text but are missing an embedding.
                cur.execute("SELECT id, full_text FROM topics WHERE full_text IS NOT NULL AND embedding IS NULL")
                topics_to_process = cur.fetchall()

                if not topics_to_process:
                    log("✅ All topics have already been embedded. Nothing to do.")
                    return

                log(f"Found {len(topics_to_process)} topics to embed. Starting process...")

                for i, (topic_id, full_text) in enumerate(topics_to_process):
                    log(f"  -> Processing topic {i+1}/{len(topics_to_process)} (ID: {topic_id})...")
                    
                    if not full_text or not full_text.strip():
                        log(f"     - Warning: Topic {topic_id} has no text. Skipping.")
                        continue

                    # Generate the embedding for the topic's full text.
                    embedding = model.encode(full_text)
                    
                    # Convert the embedding to a format that pg_vector can store.
                    embedding_list = embedding.tolist()

                    # Update the database with the new embedding.
                    cur.execute(
                        "UPDATE topics SET embedding = %s WHERE id = %s",
                        (embedding_list, topic_id)
                    )
                
            # The 'with' block automatically commits the transaction.
            log("\n✅ All new topic embeddings have been generated and saved to the database.")

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