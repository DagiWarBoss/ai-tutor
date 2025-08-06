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
    lines = []
    for page_num in range(doc.page_count):
        lines.extend(doc[page_num].get_text().split('\n'))
    headings = []
    i = 0
    # Pattern: Allow up to 5 decimals, but only at line start (not mid)
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num = match.group(1).strip()
            text = match.group(2).strip()
            # If text looks like just a section label (e.g. empty, short, or "(a)"), look ahead for real heading
            if not text or len(text) < 2 or text.strip("()").isdigit():
                lookahead = 1
                while i + lookahead < len(lines):
                    next_line = lines[i + lookahead].strip()
                    # Find next non-empty, non-numeric line to use as heading
                    if next_line and not next_line.isdigit() and not re.match(r'^\(?[a-zA-Z]\)?$', next_line):
                        text = next_line
                        i += lookahead  # Move pointer to the next used line
                        break
                    lookahead += 1
            headings.append((num, text.strip()))
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    """
    Remove lines that are very short or where heading text is just a number.
    """
    cleaned = []
    for num, text in headings:
        if not text or text.strip().isdigit() or len(text.strip()) < 2:
            continue
        cleaned.append((num, text.strip()))
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
