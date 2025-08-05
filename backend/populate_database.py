import os
import fitz  # PyMuPDF
import psycopg2
import re
import json
from dotenv import load_dotenv
from collections import Counter
from together import Together
import time

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- SECURELY GET CREDENTIALS FROM ENVIRONMENT ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# --- Initialize Together AI Client ---
llm_client = Together(api_key=TOGETHER_API_KEY)

# --- CONFIGURATION ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"

def get_candidate_headings(doc):
    """
    Stage 1: A more lenient function to extract any line that looks like a potential heading.
    """
    candidate_headings = []
    try:
        # This regex is now much less strict. It just looks for a line starting with a number pattern.
        topic_pattern = re.compile(r"^\s*(\d+[\.\d+]*)\s+(.*)", re.MULTILINE)

        for page_num in range(min(5, doc.page_count)): # Scan first 5 pages
            page_text = doc[page_num].get_text()
            matches = topic_pattern.findall(page_text)
            for match in matches:
                # Reconstruct the full line to pass to the AI
                full_line = f"{match[0]} {match[1].strip()}"
                candidate_headings.append(full_line)
        
        return candidate_headings
    except Exception as e:
        print(f"    - ❌ ERROR during candidate extraction: {e}")
        return []

def refine_topics_with_ai(headings, chapter_name):
    """Stage 2: Sends candidate headings to an LLM for final structuring and cleaning."""
    if not headings: return []
    
    headings_text = "\n".join(headings)
    try:
        system_message = (
            "You are a meticulous data extraction expert for the NCERT curriculum. Your task is to analyze the following list of candidate headings extracted from a textbook chapter. "
            "Your job is to identify and structure only the official, numbered topics and sub-topics in their correct hierarchical order. "
            "Ignore any text that is not a real topic, like 'Summary', 'Exercises', figure captions, or full sentences."
            "Your entire response MUST be a single, valid JSON object with a single key 'topics'. "
            "The value for 'topics' must be an array of objects, each with 'topic_number' and 'topic_name'."
        )
        user_message_content = f"Please refine the following candidate headings for the chapter '{chapter_name}':\n\n--- CANDIDATE HEADINGS ---\n{headings_text}\n--- END OF HEADINGS ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]

        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages, max_tokens=3000, temperature=0.0, response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content.strip()
        return json.loads(response_content).get('topics', [])
    except Exception as e:
        print(f"    - ❌ ERROR during AI refinement: {e}")
        return []

def main():
    """DEBUG SCRIPT: Processes a single file and prints intermediate steps."""
    print("--- Starting DEBUG script for Hybrid Pipeline ---")

    # --- Define the single file we want to test ---
    subject_name = "Chemistry"
    class_level = 11
    filename_to_test = "Some Basic Concepts Of Chemistry.pdf"

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)
    pdf_path = os.path.join(pdf_root_full_path, subject_name, f"Class {class_level}", filename_to_test)

    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: Test file not found at {pdf_path}. Please check the path and filename.")
        return

    try:
        doc = fitz.open(pdf_path)
        
        print("\n--- STAGE 1: CANDIDATE EXTRACTION (Less Rigid) ---")
        candidate_headings = get_candidate_headings(doc)
        print(f"\nFound {len(candidate_headings)} candidate headings:")
        for heading in candidate_headings:
            print(f"  - {heading}")
        
        print("\n--- STAGE 2: AI REFINEMENT ---")
        refined_topics = refine_topics_with_ai(candidate_headings, os.path.splitext(filename_to_test)[0])
        print(f"\nAI returned {len(refined_topics)} refined topics:")
        for topic in refined_topics:
            print(f"  - Number: {topic.get('topic_number', 'N/A')}, Name: {topic.get('topic_name', 'N/A')}")
            
        doc.close()

    except Exception as e:
        print(f"  ❌ CRITICAL ERROR processing file {filename_to_test}: {e}")
    
    print("\n--- DEBUG script finished ---")
    print("Please copy the full output from both stages and share it.")


if __name__ == '__main__':
    main()
