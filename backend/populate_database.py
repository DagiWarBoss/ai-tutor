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
    
    # --- CHANGE 1: Find where the exercises start to avoid extracting them ---
    exercises_start_index = len(lines) # Default to end of doc
    for idx, line_text in enumerate(lines):
        # Stop processing when we hit the main "EXERCISES" header
        if line_text.strip() == "EXERCISES":
            exercises_start_index = idx
            print(f"--- Found 'EXERCISES' section at line {idx}, processing will stop there. ---")
            break

    headings = []
    i = 0
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    # The loop now stops before the exercises section
    while i < exercises_start_index:
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()

            # --- CHANGE 2: Smarter loop to capture full, multi-line topic names ---
            j = i + 1
            while j < exercises_start_index:
                next_line = lines[j].strip()

                is_plausible_continuation = (
                    next_line
                    and next_line[0].isupper()
                    and len(next_line.split()) < 7 # Prevents grabbing full paragraphs
                )

                if pat.match(next_line) or not is_plausible_continuation:
                    break
                
                text += " " + next_line
                j += 1
            
            headings.append((num, text.strip()))
            i = j - 1
            # --- End of Changes ---

        i += 1
        
    doc.close()
    return headings

def post_filter(headings):
    # This filter is adjusted to work with the improved extractor
    cleaned = []
    BAD_STARTS = ('table', 'fig', 'problem', 'example')
    
    for num, text in headings:
        # Rule 1: Must be shorter than a long sentence (e.g., 12 words)
        if len(text.split()) > 12:
            continue
        # Rule 2: Exclude lines that start with junk words
        if text.lower().startswith(BAD_STARTS):
            continue
        # Rule 3: Must contain at least one letter
        if not any(char.isalpha() for char in text):
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