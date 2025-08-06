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

def is_plausible_topic_number(num, chapter_number):
    """
    Only accepts topic numbers in the form N, N.N, N.N.N where N matches the chapter_number.
    e.g., for chapter 3, accepts 3, 3.1, 3.2.1, etc.
    """
    if not num: return False
    # Accepts 1, 1.1, 1.2 etc. for chapter 1; also filters things like "1869"
    patt = fr"^{chapter_number}(?:\.\d+)*$"
    return bool(re.match(patt, num))

def get_candidate_headings(doc, chapter_num_str):
    """
    Extract lines like '1 Some Chapter', '1.1 Topic', up to 3 levels, and filter further.
    """
    candidate_headings = []
    # Improved regex: Match lines that BEGIN a line, with chapter number (not any number)
    topic_pattern = re.compile(fr"^\s*({chapter_num_str}(?:\.\d{{1,2}})*)\s+(.*)", re.MULTILINE)
    EXCLUDE_KEYWORDS = ['table', 'figure', 'exercise', 'summary', 'activity', 'example']
    for page_num in range(min(7, doc.page_count)): # Optionally, scan ~7 pages to get nested topics
        page_text = doc[page_num].get_text()
        for match in topic_pattern.finditer(page_text):
            number, name = match.groups()
            name_stripped = name.strip()
            # Skip headings that contain EXCLUDE keywords or are too long/short
            if any(kw in name_stripped.lower() for kw in EXCLUDE_KEYWORDS):
                continue
            if not (2 <= len(name_stripped.split()) <= 12):
                continue
            candidate_headings.append(f"{number} {name_stripped}")
    return candidate_headings

def refine_topics_with_ai(headings, chapter_name):
    if not headings:
        return []
    headings_text = "\n".join(headings)
    try:
        system_message = (
            "You are an expert data extractor for the NCERT curriculum. Analyze this candidate list of numbered headings from a chapter. "
            "Return only OFFICIAL, real, syllabus-like topics and subtopics (ignore 'Exercises', 'Summary', plain sentences, tables, random numbers, or page numbers). "
            "All topic numbers must be hierarchical (like 3, 3.1, 3.2.1)."
            "Your result MUST be a single, valid JSON object: {\"topics\": [{\"topic_number\": string, \"topic_name\": string}, ...]}"
        )
        user_message_content = f"Refine the candidate headings for the chapter '{chapter_name}':\n\n--- CANDIDATE HEADINGS ---\n{headings_text}\n--- END OF HEADINGS ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages, max_tokens=1800, temperature=0.0,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content.strip()
        topics = json.loads(response_content).get('topics', [])
        # Post-process (optional): Remove weird numbers, filter by chapter prefix
        filtered_topics = []
        chapter_prefix = chapter_name.strip().split()[0]   # "3" for "3. Chemical Bonding...", etc.
        for t in topics:
            num = str(t.get('topic_number', '')).strip()
            name = str(t.get('topic_name', '')).strip()
            if is_plausible_topic_number(num, chapter_prefix):
                if len(name) > 2 and not any(k in name.lower() for k in ['table', 'summary', 'exercise']):
                    filtered_topics.append({'topic_number': num, 'topic_name': name})
        return filtered_topics
    except Exception as e:
        print(f"    - ❌ ERROR during AI refinement: {e}")
        return []

def main():
    print("--- Starting Refined Bulk Chapter Processing ---")
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
                chapter_num_str = chapter_name.split()[0]  # assumes "3.2 Thermodynamics" etc.
                pdf_path = os.path.join(class_path, filename)
                print(f"\nProcessing {subject_name} / {class_folder} / {filename}")
                try:
                    doc = fitz.open(pdf_path)
                    candidate_headings = get_candidate_headings(doc, chapter_num_str)
                    print(f"Found {len(candidate_headings)} tightly-filtered candidate headings.")
                    refined_topics = refine_topics_with_ai(candidate_headings, chapter_name)
                    print(f"AI returned {len(refined_topics)} clean, syllabus topics:")
                    for topic in refined_topics:
                        print(f"  - Number: {topic.get('topic_number', 'N/A')}, Name: {topic.get('topic_name', 'N/A')}")
                    doc.close()
                    time.sleep(2)  # Rate limit for API
                except Exception as e:
                    print(f"  ❌ ERROR processing file {filename}: {e}")
    print("\n--- Processing finished ---")

if __name__ == '__main__':
    main()
