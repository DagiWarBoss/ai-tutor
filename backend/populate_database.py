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
        # Using sort=True helps maintain a logical reading order
        lines.extend(doc[page_num].get_text("text", sort=True).split('\n'))
    
    headings = []
    i = 0
    # The regex is slightly improved to catch different dash types, but the logic is the same.
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()

            # --- KEY CHANGE: Loop to capture multi-line headings ---
            # This 'while' loop replaces the previous single 'if' statement.
            # It will keep adding subsequent lines to the 'text' variable
            # as long as they appear to be continuations of the topic name.
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()

                # Stop appending if the next line is a new topic, is empty, or doesn't look like text.
                if pat.match(next_line) or not next_line or not next_line[0].isalpha():
                    break

                # Add the continuation line to the current heading text.
                text += " " + next_line
                j += 1
            
            headings.append((num, text.strip()))
            # Skip the outer loop ahead to where we finished reading.
            i = j - 1
            # --- End of Change ---

        i += 1
        
    doc.close()
    return headings

def post_filter(headings):
    # This function remains unchanged, as per your request.
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
        for num, text in filtered_headings:
            print(f"  - {num} {text}")
        print(f"\nTotal filtered matches: {len(filtered_headings)}")
    except FileNotFoundError:
        print(f"Error: The file was not found at the specified path: {pdf_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")