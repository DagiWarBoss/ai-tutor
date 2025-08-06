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
CHAPTER_NUMBER = "4"  # Change per chapter

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    lines_by_page = []
    for page_num in range(doc.page_count):
        lines_by_page.extend(doc[page_num].get_text().split('\n'))
    i = 0
    headings = []
    # Pattern catches e.g. 4, 4.1, 4.9.2, ... then some text (flexible, not only line-start)
    pat = re.compile(rf"\b{chapter_number}(?:\.\d+){{0,5}}\b[\s\.:;\-)]+(.*)$")
    while i < len(lines_by_page):
        line = lines_by_page[i].strip()
        match = pat.search(line)
        if match:
            num = re.search(rf"{chapter_number}(?:\.\d+){{0,5}}", line).group()
            text = match.group(1).strip()

            # If text is empty/short, try to join with next line (if next line is title cased)
            if (not text or len(text.split()) < 2) and i + 1 < len(lines_by_page):
                next_line = lines_by_page[i+1].strip()
                if next_line and next_line[0].isupper() and not next_line.isdigit():
                    text = next_line.strip()
                    i += 1  # consume both lines

            headings.append((num, text))
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    """
    Keep only lines likely to be real topics.
    """
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'formation', 'summary', 'state', 'discuss'
    )
    BAD_WORDS = ('molecule', 'atom', '(', ')', 'calculate', 'determine')
    MAX_WORDS = 8
    MIN_WORDS = 2

    for num, text in headings:
        t = text.strip()
        words = t.split()
        if not t or not t[0].isupper():       # must start with uppercase
            continue
        if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
            continue
        if t.lower().startswith(BAD_STARTS):
            continue
        if any(bad in t.lower() for bad in BAD_WORDS):
            continue
        # Remove lines ending in '.' (likely sentences, not topics)
        if t.endswith('.'):
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
    print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
    for num, text in filtered_headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
