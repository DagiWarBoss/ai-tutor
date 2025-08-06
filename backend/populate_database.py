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
    # KEY CHANGE: Allow ANY number of .digit groups after chapter (eg. 4, 4.7, 4.7.3...) not just up to 5.
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+)*)(?:[\s\.:;\-)]+)(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num = match.group(1).strip()
            text = match.group(2).strip()
            # If line just number or text is tiny, look ahead
            if not text or len(text.split()) < 2:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Require next line to start with uppercase & not digits
                    if next_line and next_line[0].isupper() and not next_line.isdigit():
                        text = next_line
                        i += 1
            headings.append((num, text))
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'solution', 'calculate', 'find', 'discuss',
    )
    BAD_CONTAINS = ('molecule', 'atom', '(', ')', 'equation', 'value', 'show', 'number', 'reason')
    for num, text in headings:
        t = text.strip()
        words = t.split()
        # Real headings are 2–9 words, start with Uppercase, and avoid "junk"
        if not t or not t[0].isupper():
            continue
        if len(words) < 2 or len(words) > 9:
            continue
        # Exclude table, figure, exercises, etc.
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
            continue
        if any(bad in t.lower() for bad in BAD_CONTAINS):
            continue
        # Don't allow headings ending with ":" (often captions) or "."
        if t.endswith(':') or t.endswith('.'):
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
    with open("candidate_topics.txt", "w", encoding="utf-8") as f:
        for num, text in filtered_headings:
            line = f"{num} {text}".strip()
            f.write(f"{line}\n")
            print(line)
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
