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
CHAPTER_NUMBER = "4"

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    # Looser: allow heading to start anywhere in the line, then token boundary or punctuation
    topic_pattern = re.compile(rf"\b{chapter_number}(?:\.\d+){{0,5}}\b[\s\.:;\-)]+(.+)", re.MULTILINE)
    matches = []
    for page_num in range(doc.page_count):
        page_text = doc[page_num].get_text()
        for line in page_text.split('\n'):
            # Capture heading number at start or after whitespace/punctuation (not just line start)
            found = re.findall(rf"({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.+)", line)
            for num, text in found:
                matches.append((num.strip(), text.strip()))
    doc.close()
    return matches

def post_filter(headings):
    cleaned = []
    for num, text in headings:
        # Keep only lines where the heading text starts with an uppercase letter—likely a real topic
        if not text or not text[0].isupper():
            continue
        # Exclude very short lines or stubs
        if len(text.strip()) < 3:
            continue
        # Remove lines with likely junk like molecule examples, formulas, or mid-sentences
        if any(tok in text for tok in [")", ":", "molecule", "atom", "bond", "reaction", "hydrogen atoms"]):
            # Allow 'Bond Parameters' or real topics by requiring at least 2 words and <7 words
            word_count = len(text.split())
            if word_count < 2 or word_count > 8:
                continue
        # Exclude if text contains a formula-like pattern (as a precaution)
        if re.search(r'[=+\-*/]', text):
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
