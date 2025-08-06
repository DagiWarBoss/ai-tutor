import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Change per chapter

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    lines = []
    for page_num in range(doc.page_count):
        lines.extend(doc[page_num].get_text().split('\n'))
    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()
            # If text is very short, try to join with next line (looking for Title Case start)
            if not text or len(text.split()) < 2:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and next_line[0].isupper() and not next_line.isdigit():
                        text = next_line
                        i += 1
            headings.append((num, text))
        i += 1
    doc.close()
    return headings

def is_title_case(text):
    # Return True if every word is capitalized and alphabetic (like NCERT headings)
    words = text.split()
    return all(w[0].isupper() and w[1:].islower() and w.isalpha() for w in words if len(w) > 1)

def post_filter(headings):
    cleaned = []
    MIN_WORDS = 2
    MAX_WORDS = 10
    for num, text in headings:
        stripped = text.strip()
        words = stripped.split()
        if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
            continue
        # True NCERT headings are Title Case (every word capitalized)
        if not is_title_case(stripped):
            continue
        cleaned.append((num, stripped))
    return cleaned

if __name__ == '__main__':
    pdf_path = os.path.join(
        script_dir, PDF_ROOT_FOLDER,
        "Chemistry", "Class 11", TARGET_CHAPTER
    )
    headings = extract_chapter_headings(pdf_path, CHAPTER_NUMBER)
    filtered_headings = post_filter(headings)
    print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
    for num, text in filtered_headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
