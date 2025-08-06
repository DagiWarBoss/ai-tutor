import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Adjust per chapter

def extract_chapter_headings(pdf_path, chapter_number):
    doc = fitz.open(pdf_path)
    headings = []
    lines_by_page = []
    for page_num in range(doc.page_count):
        lines_by_page.extend(doc[page_num].get_text().split('\n'))
    i = 0
    while i < len(lines_by_page):
        line = lines_by_page[i].strip()
        # Allow chapter number + up to 5 decimals, anywhere in the line
        match = re.match(rf".*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)", line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()
            # If text is too short or looks incomplete, peek at next line for possible heading continuation
            if len(text) < 3 and i + 1 < len(lines_by_page):
                next_line = lines_by_page[i+1].strip()
                # Use next line as topic if it starts with an uppercase letter and looks like a topic (not just a number)
                if next_line and next_line[0].isupper() and not next_line.isdigit():
                    text = next_line
                    i += 1  # Skip the next line since we've used it
            headings.append((num, text))
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    # Remove lines where text is only a number, too short, or doesn't resemble a true topic
    for num, text in headings:
        if not text or text.strip().isdigit():
            continue
        if len(text.strip()) < 3:
            continue
        # Remove lines likely from mid-sentence or exercises—those without initial uppercase and two+ words
        if not text[0].isupper():
            continue
        if len(text.split()) < 2 and not num.count(".") > 0:  # Require at least 2 words for subtopics
            continue
        # Optional: ignore lines with molecule, atom, etc. not at topic start
        if any(tok in text.lower() for tok in ["hydrogen atoms", "molecule", "atom", "bond", "="]):
            if not (text.lower().startswith("bond") or text.lower().startswith("types of") or text.lower().startswith("hybridisation")):
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
