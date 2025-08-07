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
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()

            # --- UPDATED: Combine multiline headings ---
            if not text or len(text.split()) < 3:
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and next_line[0].isupper() and not next_line.isdigit():
                        text += " " + next_line
                        j += 1
                        if len(text.split()) >= 4 and not text.endswith((':', '.', ';')):
                            break
                    else:
                        break
                i = j - 1  # Skip the lines we've already consumed

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
        if not t or not t[0].isupper():
            continue
        if len(words) < 2 or len(words) > 9:
            continue
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
            continue
        if any(bad in t.lower() for bad in BAD_CONTAINS):
            continue
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
    print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
    for num, text in filtered_headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
