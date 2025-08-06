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
CHAPTER_NUMBER = "4"  # Set to "4" for this chapter

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
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

if __name__ == '__main__':
    pdf_path = os.path.join(
        script_dir, PDF_ROOT_FOLDER,
        "Chemistry", "Class 11", TARGET_CHAPTER
    )
    headings = extract_chapter_headings(pdf_path, CHAPTER_NUMBER)
    print(f"\nMatched candidate headings for '{TARGET_CHAPTER}':")
    for num, text in headings:
        print(f"  - {num} {text}")
    print(f"\nTotal matched: {len(headings)}")
