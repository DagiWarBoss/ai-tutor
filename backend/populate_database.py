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
    # Pattern matches section numbers like 4, 4.1, 4.2.3, etc.
    pat = re.compile(rf'^\s*({chapter_number}(?:\.\d+)*)(?:[\s\.:;\-)]+)?(.*)$')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num = match.group(1).strip()
            text = match.group(2).strip()
            collected = text

            # If text after number is missing or too short, check next 1-2 lines as possible heading continuation
            lookforward = 0
            while (not collected or len(collected.split()) < 4) and (i + 1 + lookforward) < len(lines) and lookforward < 2:
                next_line = lines[i + 1 + lookforward].strip()
                # Only join if next line starts with uppercase/lowercase letter and is not another section
                if next_line and not pat.match(next_line) and not next_line[0].isdigit():
                    collected += ' ' + next_line
                    lookforward += 1
                else:
                    break
            headings.append((num, collected.strip()))
            i += lookforward  # skip any merged lines
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'solution', 'calculate', 'find', 'discuss',
    )
    # Only filter headings that are empty, not capitalized, or suspiciously short/long
    for num, text in headings:
        t = text.strip()
        words = t.split()
        if not t or not t[0].isupper():
            continue
        if len(words) < 2 or len(words) > 18:
            continue
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
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
    with open("candidate_topics.txt", "w", encoding="utf-8") as f:
        for num, text in filtered_headings:
            line = f"{num} {text}".strip()
            f.write(f"{line}\n")
            print(line)
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
