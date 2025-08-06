import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Set to "4" for this chapter; change for others!

def print_debug_candidates(pdf_path, chapter_number, max_pages=None):
    print(f"--- DEBUGGING: Regex Extraction for '{os.path.basename(pdf_path)}' ---")
    doc = fitz.open(pdf_path)
    # Robust regex: Matches chapter_number, subtopics, up to 5 deep (e.g. 4, 4.1, 4.9.2, 4.10.3.4, etc.)
    pattern = rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.+)"
    topic_pattern = re.compile(pattern, re.MULTILINE)
    matches = []
    pages = range(doc.page_count) if not max_pages else range(min(max_pages, doc.page_count))
    for page_num in pages:
        page_text = doc[page_num].get_text()
        lines = page_text.split('\n')
        print(f"\n----- PAGE {page_num+1} (first 300 chars) -----")
        print('|'.join(lines[:10]))  # Show up to first 10 lines for context
        for idx, line in enumerate(lines):
            match = topic_pattern.match(line)
            if match:
                n, txt = match.group(1), match.group(2)
                matches.append((n.strip(), txt.strip(), page_num+1, idx+1, line.strip()))
                print(f"[MATCH] Page {page_num+1}, Line {idx+1}: NUM='{n.strip()}' | TEXT='{txt.strip()}' | RAW='{line.strip()}'")
    print(f"\n[SUMMARY] Total matches found: {len(matches)}")
    for n, txt, p, l, raw in matches:
        print(f"    {n} | {txt} | page:{p} line:{l} | RAW: {raw}")
    doc.close()
    print("[INFO] Done printing candidate headings (regex Stage 1).\n")

if __name__ == '__main__':
    pdf_path = os.path.join(
        script_dir, PDF_ROOT_FOLDER,
        "Chemistry", "Class 11", TARGET_CHAPTER
    )
    print_debug_candidates(pdf_path, CHAPTER_NUMBER, max_pages=None)  # None = all pages
