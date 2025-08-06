import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

# --- Setup environment ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Change this for each chapter as needed

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    # Captures headings like 4, 4.1, ..., 4.9.2 etc., up to 5 sub-levels.
    topic_pattern = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.+)", re.MULTILINE)
    matches = []
    for page_num in range(doc.page_count):
        page_text = doc[page_num].get_text()
        for line in page_text.split('\n'):
            match = topic_pattern.match(line)
            if match:
                num, text = match.group(1).strip(), match.group(2).strip()
                matches.append((num, text))
    doc.close()
    return matches

def post_filter(headings):
    """
    Remove entries where text is just a number or too short—cleans out
    exercise numbers, page headers, and incomplete/broken lines.
    """
    cleaned = []
    for num, text in headings:
        if text.strip().isdigit():
            continue
        if len(text.strip()) < 3:
            continue
        cleaned.append((num, text))
    return cleaned

if __name__ == '__main__':
    pdf_path = os.path.join(
        script_dir, PDF_ROOT_FOLDER,
        "Chemistry", "Class 11", TARGET_CHAPTER
    )
    headings = extract_chapter_headings(pdf_path, CHAPTER_NUMBER)
    filtered_headings = post_filter(headings)
    print(f"\nMatched candidate headings for '{TARGET_CHAPTER}':")
    for num, text in filtered_headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
