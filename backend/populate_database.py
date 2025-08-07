import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Change per chapter

def extract_chapter_headings(pdf_path, chapter_number):
    # This function is UNCHANGED, as you requested.
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
            num, text = match.group(1).strip(), match.group(2).strip()
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
    # This list is UNCHANGED.
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'solution', 'calculate', 'find', 'discuss',
    )
    
    # --- CHANGE 1: 'molecule' and 'atom' are removed from this list ---
    # These words are essential for chemistry topics and should not be filtered out.
    BAD_CONTAINS = ('(', ')', 'equation', 'value', 'show', 'number', 'reason')
    
    for num, text in headings:
        t = text.strip()
        words = t.split()
        
        # This rule is UNCHANGED.
        if not t or not t[0].isupper():
            continue
            
        # --- CHANGE 2: Word count limit is increased from 9 to 12 ---
        # This allows longer but valid topic names to be included.
        if len(words) < 2 or len(words) > 12:
            continue
            
        # These rules are UNCHANGED.
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
            continue
        if any(bad in t.lower() for bad in BAD_CONTAINS):
            continue
        if t.endswith(':') or t.endswith('.'):
            continue
            
        cleaned.append((num, text))
    return cleaned

if __name__ == '__main__':
    # This section is UNCHANGED.
    try:
        pdf_path = os.path.join(
            script_dir, PDF_ROOT_FOLDER,
            "Chemistry", "Class 11", TARGET_CHAPTER
        )
        headings = extract_chapter_headings(pdf_path, CHAPTER_NUMBER)
        filtered_headings = post_filter(headings)
        
        print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
        if not filtered_headings:
            print("  - No headings found that match the filter criteria.")
        else:
            for num, text in filtered_headings:
                print(f"  - {num} {text}")
        
        print(f"\nTotal filtered matches: {len(filtered_headings)}")

    except FileNotFoundError:
        print(f"Error: The file was not found at the specified path: {pdf_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")