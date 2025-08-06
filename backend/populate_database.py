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

QUESTION_PREFIXES = [
    "write", "define", "explain", "describe", "what", "how", "why", "calculate", "draw",
    "compare", "arrange", "distinguish", "find", "show", "state", "discuss", "which", "give", "name"
]

def filter_candidates(candidates):
    filtered = []
    for cand in candidates:
        if not cand.strip():
            continue
        parts = cand.strip().split(" ", 1)
        if len(parts) != 2:
            continue
        num, text = parts
        # Numeric noise filter: page numbers, years, etc.
        try:
            if num.isdigit():
                n = int(num)
                if n > 50 and n < 3000:  # Skip probable page/question numbers
                    continue
                if 1900 < n < 2100:     # Skip probable years
                    continue
        except ValueError:
            pass
        lowtext = text.strip().lower()
        # Remove single-section-headings
        if lowtext in ["chemistry", "physics", "mathematics"]:
            continue
        # Remove lines with less than 2 words or clear equations
        words = text.strip().split()
        if len(words) < 2:
            continue
        if any(op in text for op in ['=', '+', '-', '*', '/', 'sin', 'cos', 'tan', 'π', 'roots']):
            continue
        # Remove questions/verbs lines (at beginning)
        first_word = words[0].lower()
        if first_word in QUESTION_PREFIXES:
            continue
        if any(text.lower().startswith(q) for q in QUESTION_PREFIXES):
            continue
        filtered.append(cand)
    return filtered

def get_candidate_headings(doc):
    candidate_headings = []
    # Any line with "number dot text" style
    topic_pattern = re.compile(r"^\s*(\d{1,3}(?:\.\d+){0,3})[\s\.:;-]+(.{2,80})", re.MULTILINE)
    for page_num in range(doc.page_count):
        page_text = doc[page_num].get_text()
        print(f"\n----- PAGE {page_num+1} (first 100 chars) -----")
        print(page_text[:100], "\n")
        matches = topic_pattern.findall(page_text)
        print(f"[DEBUG] Found {len(matches)} regex matches on page {page_num+1}.")
        for match in matches:
            number = match[0]
            name_stripped = match[1].strip()
            cand = f"{number} {name_stripped}"
            candidate_headings.append(cand)
            print(f"  [RAW] {cand}")
    print(f"\n[DEBUG] Total raw candidate headings found: {len(candidate_headings)}")
    filtered = filter_candidates(candidate_headings)
    print(f"[DEBUG] Filtered candidates to {len(filtered)} lines that look like real topics.")
    for h in filtered:
        print(f"  [CANDIDATE] {h}")
    if not filtered:
        print("[DEBUG] WARNING: No viable headings after filtering. Tune your regex/filters!")
    return filtered

def refine_topics_with_ai(headings, chapter_name):
    if not headings:
        print("[DEBUG] No candidate headings to send to LLM.")
        return []
    headings_text = "\n".join(headings)
    try:
        system_message = (
            "You are an NCERT syllabus data extractor. Given candidate headings, "
            "return only genuine hierarchical topics/subtopics (numbered like X, X.X, X.X.X). "
            "Ignore headings that are just page numbers, years, math expressions, single words, or questions. "
            "Return strict JSON: {\"topics\": [{\"topic_number\": string, \"topic_name\": string}, ...]}"
            "Skip exercises, summary, tables, figure captions, or incomplete/question lines."
        )
        user_message_content = f"Refine candidate headings for '{chapter_name}':\n---\n{headings_text}\n---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages, max_tokens=1500, temperature=0.0,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content.strip()
        print(f"\n[DEBUG] LLM output:\n{response_content}\n")
        topics = json.loads(response_content).get('topics', [])
        filtered = []
        for t in topics:
            num = str(t.get('topic_number', ''))
            name = str(t.get('topic_name', ''))
            if num and name and 1 <= len(num) <= 10 and len(name.split()) >= 2:
                filtered.append({'topic_number': num, 'topic_name': name})
        return filtered
    except Exception as e:
        print(f"    - ❌ ERROR during LLM refinement: {e}")
        return []

def main():
    print("--- Starting All-Chapter NCERT Debug Extraction (Questions-Reduced) ---")
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
                    print(f"\n[INFO] Filtered headings for {chapter_name}:")
                    for h in candidate_headings:
                        print(f"    - {h}")
                    refined_topics = refine_topics_with_ai(candidate_headings, chapter_name)
                    print(f"[INFO] AI returned {len(refined_topics)} syllabus topics:")
                    for topic in refined_topics:
                        print(f"    - Number: {topic['topic_number']} | Name: {topic['topic_name']}")
                    doc.close()
                    time.sleep(2.0)  # API limits
                except Exception as e:
                    print(f"  ❌ ERROR processing file {filename}: {e}")
    print("\n--- SCRIPT FINISHED ---")

if __name__ == '__main__':
    main()
