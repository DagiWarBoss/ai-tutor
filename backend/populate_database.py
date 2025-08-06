import os
import fitz  # PyMuPDF
import re
import json
from dotenv import load_dotenv
from together import Together
import time

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
llm_client = Together(api_key=TOGETHER_API_KEY)

def get_candidate_headings(doc):
    topic_pattern = re.compile(r"^\s*(\d+[\.\d+]*)\s+(.*)", re.MULTILINE)
    candidate_headings = []
    for page_num in range(min(5, doc.page_count)): # Scan first 5 pages
        page_text = doc[page_num].get_text()
        matches = topic_pattern.findall(page_text)
        for match in matches:
            full_line = f"{match[0]} {match[1].strip()}"
            candidate_headings.append(full_line)
    return candidate_headings

def refine_topics_with_ai(headings, chapter_name):
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
    print("--- Starting Bulk Chapter Processing with Hybrid Pipeline ---")
    root = os.path.join(script_dir, PDF_ROOT_FOLDER)
    for subject_name in os.listdir(root):
        subject_path = os.path.join(root, subject_name)
        if not os.path.isdir(subject_path):
            continue
        for class_folder in os.listdir(subject_path):
            class_path = os.path.join(subject_path, class_folder)
            if not os.path.isdir(class_path):
                continue
            for filename in os.listdir(class_path):
                if not filename.lower().endswith(".pdf"):
                    continue
                chapter_name = os.path.splitext(filename)[0]
                pdf_path = os.path.join(class_path, filename)
                print(f"\nProcessing {subject_name} / {class_folder} / {filename}")
                try:
                    doc = fitz.open(pdf_path)
                    candidate_headings = get_candidate_headings(doc)
                    print(f"Found {len(candidate_headings)} candidate headings.")
                    refined_topics = refine_topics_with_ai(candidate_headings, chapter_name)
                    print(f"AI returned {len(refined_topics)} refined topics:")
                    for topic in refined_topics:
                        print(f"  - Number: {topic.get('topic_number', 'N/A')}, Name: {topic.get('topic_name', 'N/A')}")
                    doc.close()
                    time.sleep(1.5)  # Rate limit AI calls
                except Exception as e:
                    print(f"  ❌ ERROR processing file {filename}: {e}")
    print("\n--- Bulk processing finished ---")

if __name__ == '__main__':
    main()
