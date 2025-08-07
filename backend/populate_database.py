import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
# NOTE: Adjusted to handle cases where __file__ might not be defined (e.g., in a notebook)
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
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
    
    print("--- [DEBUG] Starting Heading Extraction ---")
    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
    
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            # --- DEBUG STATEMENT ADDED ---
            print(f"\n[DEBUG] Regex Matched Line: '{line}'")
            num, text = match.group(1).strip(), match.group(2).strip()
            
            if not text or len(text.split()) < 2:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and next_line[0].isupper() and not next_line.isdigit():
                        # --- DEBUG STATEMENT ADDED ---
                        print(f"[DEBUG] Heading text is short. Looking at next line: '{next_line}'")
                        print(f"[DEBUG] ERROR POINT: Replacing '{text}' with '{next_line}' instead of combining.")
                        text = next_line
                        i += 1
            headings.append((num, text))
        i += 1
        
    doc.close()
    print("--- [DEBUG] Finished Heading Extraction ---")
    return headings

def post_filter(headings):
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'solution', 'calculate', 'find', 'discuss',
    )
    BAD_CONTAINS = ('molecule', 'atom', '(', ')', 'equation', 'value', 'show', 'number', 'reason')
    
    print("\n--- [DEBUG] Starting Post-Filter ---")
    for num, text in headings:
        print(f"\n[DEBUG] Filtering -> '{num} {text}'")
        t = text.strip()
        words = t.split()
        
        # --- DEBUG STATEMENTS ADDED FOR EACH RULE ---
        if not t or not t[0].isupper():
            print(f"  └─ REJECTED: Does not start with an uppercase letter.")
            continue
            
        if len(words) < 2 or len(words) > 9:
            print(f"  └─ REJECTED: Word count is {len(words)} (must be 2-9).")
            continue
            
        rejected = False
        for bad in BAD_STARTS:
            if t.lower().startswith(bad):
                print(f"  └─ REJECTED: Starts with banned word '{bad}'.")
                rejected = True
                break
        if rejected:
            continue

        for bad in BAD_CONTAINS:
            if bad in t.lower():
                print(f"  └─ REJECTED: ERROR POINT -> Contains banned word '{bad}'.")
                rejected = True
                break
        if rejected:
            continue
            
        if t.endswith(':') or t.endswith('.'):
            print(f"  └─ REJECTED: Ends with ':' or '.'.")
            continue
        
        print("  └─ ACCEPTED: Heading passed all filters.")
        cleaned.append((num, text))
        
    print("\n--- [DEBUG] Post-Filter Finished ---")
    return cleaned

if __name__ == '__main__':
    try:
        pdf_path = os.path.join(
            script_dir, PDF_ROOT_FOLDER,
            "Chemistry", "Class 11", TARGET_CHAPTER
        )
        headings = extract_chapter_headings(pdf_path, CHAPTER_NUMBER)
        filtered_headings = post_filter(headings)
        
        print(f"\n--- FINAL RESULTS ---")
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