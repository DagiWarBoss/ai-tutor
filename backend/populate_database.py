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

def filter_candidates(candidates):
    filtered = []
    for cand in candidates:
        # Remove obvious non-headings: equations, single-word, math symbols
        if not cand.strip():
            continue
        parts = cand.strip().split(" ", 1)
        if len(parts) != 2: continue
        num, text = parts
        if len(text.strip().split()) < 2:
            continue
        if any(op in text for op in ['=', '+', '-', '*', '/', 'sin', 'cos', 'tan', 'π', 'roots']):
            continue
        filtered.append(cand)
    return filtered

def get_candidate_headings(doc):
    candidate_headings = []
    topic_pattern = re.compile(r"^\s*(\d{1,3}(?:\.\d+){0,3})[\s\.:;-]+(.{2,80})", re.MULTILINE)
    for page_num in range(doc.page_count):
        page_text = doc[page_num].get_text()
        matches = topic_pattern.findall(page_text)
        for match in matches:
            number = match[0]
            name_stripped = match[1].strip()
            candidate_headings.append(f"{number} {name_stripped}")
    return filter_candidates(candidate_headings)

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def refine_topics_with_ai(headings, chapter_name):
    results = []
    seen = set()
    chunk_size = 15  # Test and adjust as needed for your LLM and chapter size
    for chunk in chunked(headings, chunk_size):
        headings_text = "\n".join(chunk)
        system_message = (
            "You are an expert at extracting textbook syllabus structures from NCERT material. "
            "Given a list of chapter-numbered headings, return ONLY the actual topics/subtopics that would appear in the book's Table of Contents. "
            "DO NOT include any exercises, end-of-chapter questions, examples, or instructions—even if they appear numbered. "
            "Include official syllabus headings for every topic or subtopic, at any depth (like 4.8, 4.9.2, etc). "
            "Return only this JSON: {\"topics\": [{\"topic_number\": string, \"topic_name\": string}, ...]}."
        )
        user_message_content = f"Extract official syllabus headings for '{chapter_name}':\n---\n{headings_text}\n---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        try:
            response = llm_client.chat.completions.create(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                messages=messages,
                max_tokens=1500,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            response_content = response.choices[0].message.content.strip()
            topics = json.loads(response_content).get('topics', [])
            for t in topics:
                key = (t.get('topic_number', '').strip(), t.get('topic_name', '').strip())
                if key not in seen and key[0] and key[1] and len(key[1].split()) >= 2:
                    results.append({'topic_number': key[0], 'topic_name': key[1]})
                    seen.add(key)
            time.sleep(2)  # Rate limiting
        except Exception as e:
            print(f"    - ❌ ERROR during LLM chunk refinement: {e}")
            continue
    return results

def main():
    print("--- NCERT Extraction with LLM (Always-updating code) ---")
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
                    print(f"\n[INFO] Matched headings for {chapter_name}:")
                    for h in candidate_headings:
                        print(f"    - {h}")
                    refined_topics = refine_topics_with_ai(candidate_headings, chapter_name)
                    print(f"[INFO] AI returned {len(refined_topics)} syllabus topics:")
                    for topic in refined_topics:
                        print(f"    - Number: {topic['topic_number']} | Name: {topic['topic_name']}")
                    doc.close()
                except Exception as e:
                    print(f"  ❌ ERROR processing file {filename}: {e}")
    print("\n--- SCRIPT FINISHED ---")

if __name__ == '__main__':
    main()
