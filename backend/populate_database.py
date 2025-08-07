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

def looks_like_section(line, chapter_number):
    # e.g., "4", "4.1", "4.1.1"
    pat = re.compile(rf"^\s*{chapter_number}(?:\.\d+)*[\s\.:;\-)]+")
    return bool(pat.match(line))

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    lines = []
    for page_num in range(doc.page_count):
        lines.extend(doc[page_num].get_text().split('\n'))

    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+)*)(?:[\s\.:;\-)]+)(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num = match.group(1).strip()
            text = match.group(2).strip()
            # If text is empty or short, grab next one(s) until heading appears complete
            j = i + 1
            while True:
                # If next line looks like a new numbered topic, OR is blank, OR is clearly table/figure/example, stop.
                if j >= len(lines):
                    break
                next_line = lines[j].strip()
                if not next_line:
                    break
                if looks_like_section(next_line, chapter_number):
                    break
                if next_line.lower().startswith(("table", "figure", "exercise", "problem", "example")):
                    break
                # Otherwise, treat as part of this heading
                text = text + " " + next_line
                j += 1
            headings.append((num, text.strip()))
            i = j  # Move to after heading
        else:
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
        if len(words) < 2 or len(words) > 15:
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
    with open("candidate_topics.txt", "w", encoding="utf-8") as f:
        for num, text in filtered_headings:
            line = f"{num} {text}".strip()
            f.write(f"{line}\n")
            print(line)
    print(f"\nTotal filtered matches: {len(filtered_headings)}")
