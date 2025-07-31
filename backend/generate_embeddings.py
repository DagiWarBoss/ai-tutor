import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np

# --- Explicitly load the .env file from the backend directory ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- SECURELY GET CREDENTIALS FROM ENVIRONMENT ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- CONFIGURATION ---
# We will use a popular, high-performance model from Hugging Face.
# The first time you run this, it will download the model (a few hundred MB).
MODEL_NAME = 'all-MiniLM-L6-v2'

def main():
    """
    Connects to the database, generates embeddings for chapters that don't have them,
    and saves them back to the database.
    """
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Ensure .env file is correct.")
        return

    print("Loading sentence transformer model...")
    # This will download the model from the internet the first time it's run.
    model = SentenceTransformer(MODEL_NAME)
    print("✅ Model loaded successfully.")

    conn = None
    try:
        conn_string = f"dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}' host='{DB_HOST}' port='{DB_PORT}'"
        with psycopg2.connect(conn_string) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                # Fetch all chapters that have not yet been embedded.
                # This makes the script safely re-runnable.
                cur.execute("SELECT id, full_text FROM chapters WHERE embedding IS NULL")
                chapters_to_process = cur.fetchall()

                if not chapters_to_process:
                    print("✅ All chapters have already been embedded. Nothing to do.")
                    return

                print(f"Found {len(chapters_to_process)} chapters to embed. Starting process...")

                for i, (chapter_id, full_text) in enumerate(chapters_to_process):
                    print(f"  -> Processing chapter {i+1}/{len(chapters_to_process)} (ID: {chapter_id})...")
                    
                    if not full_text or not full_text.strip():
                        print(f"    - Warning: Chapter {chapter_id} has no text. Skipping.")
                        continue

                    # Generate the embedding for the chapter's full text.
                    embedding = model.encode(full_text)
                    
                    # Convert the embedding to a format that pg_vector can store.
                    embedding_list = embedding.tolist()

                    # Update the database with the new embedding.
                    cur.execute(
                        "UPDATE chapters SET embedding = %s WHERE id = %s",
                        (embedding_list, chapter_id)
                    )
                
                # The 'with' block automatically commits the transaction here.
                print("\n✅ All new embeddings have been generated and saved to the database.")

    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        print("  The transaction has been rolled back.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        print("\nScript finished.")


if __name__ == '__main__':
    main()
