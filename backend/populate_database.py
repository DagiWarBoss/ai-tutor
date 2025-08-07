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

    # --- FIX #1: Find where the exercises start to avoid extracting them ---
    exercises_start_index = len(lines)
    for idx, line_text in enumerate(lines):
        if line_text.strip() == "EXERCISES":
            exercises_start_index = idx
            break

    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    # The loop now correctly stops before reaching the exercises section
    while i < exercises_start_index:
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()

            # --- FIX #2: Properly combine multi-line headings ---
            # This new loop correctly appends text instead of replacing it.
            j = i + 1
            while j < exercises_start_index:
                next_line = lines[j].strip()
                # A good continuation is short and starts with a capital letter
                is_plausible_continuation = (
                    next_line
                    and next_line[0].isupper()
                    and len(next_line.split()) < 7
                )
                if pat.match(next_line) or not is_plausible_continuation:
                    break
                text += " " + next_line
                j += 1
            
            headings.append((num, text.strip()))
            i = j - 1

        i += 1
        
    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    # This list is relaxed to avoid filtering valid topics
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'calculate', 'find', 'discuss',
    )
    # --- FIX #3: Removed overly strict "bad words" ---
    BAD_CONTAINS = ('(', ')', 'equation', 'value', 'show', 'reason')
    
    for num, text in headings:
        t = text.strip()
        words = t.split()

        # Word count is increased to allow for longer, valid headings
        if len(words) < 2 or len(words) > 15:
            continue

        if not t or not t[0].isupper():
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