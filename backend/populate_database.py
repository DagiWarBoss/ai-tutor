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
    """
    Debug version: shows page text, raw matches, skip/exclude reasons.
    """
    candidate_headings = []
    # Relaxed regex: any line starting with outline type numbers (1, 1.1, 1.2.3)
    topic_pattern = re.compile(r"^\s*(\d+(\.\d+){0,3})[\s\.:;-]+(.{2,80})", re.MULTILINE)
    EXCLUDE_KEYWORDS = ['table', 'figure', 'exercise', 'summary', 'activity', 'example']

    for page_num in range(doc.page_count):
        page_text = doc[page_num].get_text()
        print(f"\n----- PAGE {page_num+1} (first 250 chars) -----")
        print(page_text[:250], "\n")
        matches = topic_pattern.findall(page_text)
        print(f"[DEBUG] Found {len(matches)} regex matches on page {page_num+1}.")

        for match in matches:
            number = match[0]
            name_stripped = match[2].strip()
            if any(kw in name_stripped.lower() for kw in EXCLUDE_KEYWORDS):
                print(f"  [SKIP: keyword] {number} {name_stripped}")
                continue
            if not (2 <= len(name_stripped.split()) <= 18):
                print(f"  [SKIP: length] {number} {name_stripped}")
                continue
            candidate_headings.append(f"{number} {name_stripped}")
            print(f"  [CANDIDATE] {number} {name_stripped}")

    print(f"\n[DEBUG] Total candidate headings found: {len(candidate_headings)}")
    if not candidate_headings:
        print("[DEBUG] WARNING: No headings found. Review regex/PDF.")
    return candidate_headings

def refine_topics_with_ai(headings, chapter_name):
    """
    Calls LLM to refine candidate list (returns good structure or nothing if broken).
    """
    if not headings:
        print("[DEBUG] No candidate headings to send to LLM.")
        return []
    headings_text = "\n".join(headings)
    try:
        system_message = (
            "You are an NCERT syllabus data extractor. Given the following candidate headings, "
            "return only real official topics/subtopics (numbered like 1.1, 2, 2.2.3). "
            "Your JSON format must be: {\"topics\": [{\"topic_number\": string, \"topic_name\": string}, ...]}"
            "Skip exercises, summary, sentences or anything that is not a curricular topic!"
        )
        user_message_content = f"Refine candidate headings for '{chapter_name}':\n---\n{headings_text}\n---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages, max_tokens=1500, temperature=0.0,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content.strip()
        print(f"\n[DEBUG] LLM raw output:\n{response_content}\n")
        topics = json.loads(response_content).get('topics', [])
        filtered = []
        for t in topics:
            num = str(t.get('topic_number', ''))
            name = str(t.get('topic_name', ''))
            if num and name and 1 <= len(num) <= 8 and len(name.split()) >= 2:
                filtered.append({'topic_number': num, 'topic_name': name})
        return filtered
    except Exception as e:
        print(f"    - ❌ ERROR during LLM refinement: {e}")
        return []

def main():
    print("--- Starting All-Chapter NCERT Debug Extraction ---")
    root = os.path.join(script_dir, PDF_ROOT_FOLDER)
    for subject_name in os.listdir(root):
        subject_path = os.path.join(root, subject_name)
        if not os.path.isdir(subject_path): continue
        for class_folder in os.listdir(subject_path):
            class_path = os.path.join(subject_path, class_folder)
            if not os.path.isdir(class_path): continue
            for filename in os.listdir(class_path):
                if not filename.lower().endswith(".pdf"): continue
                chapter_name = os.path.splitext(filename)[0]
                pdf_path = os.path.join(class_path, filename)
                print(f"\n=== Processing {subject_name} / {class_folder} / {filename} ===")
                try:
                    doc = fitz.open(pdf_path)
                    candidate_headings = get_candidate_headings(doc)
                    print(f"\n[INFO] Candidate headings for {chapter_name}:")
                    for h in candidate_headings:
                        print(f"    - {h}")
                    refined_topics = refine_topics_with_ai(candidate_headings, chapter_name)
                    print(f"[INFO] AI returned {len(refined_topics)} clean topics:")
                    for topic in refined_topics:
                        print(f"    - Number: {topic['topic_number']} | Name: {topic['topic_name']}")
                    doc.close()
                    time.sleep(1.7)  # stay within API limits
                except Exception as e:
                    print(f"  ❌ ERROR processing file {filename}: {e}")
    print("\n--- DEBUG SCRIPT FINISHED ---")

if __name__ == '__main__':
    main()
