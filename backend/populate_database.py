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
    doc = fitz.open(pdf_path)
    lines = []
    for page_num in range(doc.page_count):
        lines.extend(doc[page_num].get_text("text", sort=True).split('\n'))
    
    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()

            # --- KEY FIX: Smarter look-ahead loop ---
            # This loop now has stricter rules for what counts as a heading continuation.
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()

                # A valid continuation line must be short and start with an uppercase letter.
                # It cannot be a new heading itself or be an empty line.
                is_plausible_continuation = (
                    next_line 
                    and next_line[0].isupper() 
                    and len(next_line.split()) < 7 # Prevents grabbing full sentences
                )

                if pat.match(next_line) or not is_plausible_continuation:
                    break

                # Append the valid continuation line
                text += " " + next_line
                j += 1
            
            headings.append((num, text.strip()))
            i = j - 1  # Skip ahead past the lines we just processed
            # --- End of Fix ---

        i += 1
        
    doc.close()
    return headings

def post_filter(headings):
    # This function is UNCHANGED. The problem was in the extraction.
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