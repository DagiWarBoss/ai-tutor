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

    # Matches things like 4, 4.1, 4.1.2 etc.
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+)*)[\s\.:;\-)]+(.*)$")

    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)

        if match:
            num = match.group(1).strip()
            text = match.group(2).strip()

            # Greedily append more lines if heading looks incomplete
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if re.match(rf"^\s*{chapter_number}(?:\.\d+)*[\s\.:;\-)]+", next_line):
                    break  # next heading
                if next_line and next_line[0].isupper():
                    text += " " + next_line
                j += 1
            i = j - 1  # move i to before next heading

            headings.append((num, text))
        i += 1

    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw',
        'how', 'why', 'define', 'explain', 'calculate', 'find', 'discuss',
    )

    for num, text in headings:
        t = text.strip()
        words = t.split()
        if not t:
            continue
        if len(words) < 1 or len(words) > 20:
            continue
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
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
