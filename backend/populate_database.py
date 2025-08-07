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
    
    # Pattern: Allow up to 5 decimals, but only at line start (not mid)
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
    
    while i < len(lines):
        line = lines[i].strip()
        match = pat.match(line)
        if match:
            num, text = match.group(1).strip(), match.group(2).strip()
            
            # If text is empty or very short, look ahead for continuation
            if not text or len(text.split()) < 2:
                # Look ahead up to 2 lines for continuation
                for look_ahead in range(1, 3):
                    if i + look_ahead < len(lines):
                        next_line = lines[i + look_ahead].strip()
                        # Skip empty lines and lines that start with numbers (likely new headings)
                        if next_line and not re.match(r'^\d+', next_line):
                            # If next line starts with uppercase and doesn't look like a new heading
                            if next_line and next_line[0].isupper():
                                # Only add if the next line looks like a proper heading continuation
                                # (not too long, doesn't contain explanatory words)
                                words = next_line.split()
                                if len(words) <= 6 and not any(word.lower() in ['is', 'are', 'the', 'and', 'of', 'in', 'to', 'for', 'with', 'by'] for word in words[:2]):
                                    if text:
                                        text = text + " " + next_line
                                    else:
                                        text = next_line
                                    i += look_ahead
                                    break
                                else:
                                    # This looks like explanatory text, stop here
                                    break
                            
                            # Also check if next line continues the current text (lowercase continuation)
                            elif next_line and next_line[0].islower() and text:
                                # Only add if it's a short continuation (likely part of the heading)
                                if len(next_line.split()) <= 3:
                                    text = text + " " + next_line
                                    i += look_ahead
                                    break
                                else:
                                    # Too long, likely explanatory text
                                    break
            
            # Only add if we have meaningful text
            if text and len(text.strip()) > 0:
                headings.append((num, text.strip()))
        i += 1
    doc.close()
    return headings

def post_filter(headings):
    cleaned = []
    BAD_STARTS = (
        'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw', 'how',
        'why', 'define', 'explain', 'formation of', 'solution', 'calculate', 'find', 'discuss',
    )
    # Reduced BAD_CONTAINS to be less aggressive
    BAD_CONTAINS = ('equation', 'value', 'show', 'number', 'reason')
    
    for num, text in headings:
        t = text.strip()
        words = t.split()
        
        # Skip if no text or doesn't start with uppercase
        if not t or not t[0].isupper():
            continue
            
        # More lenient word count - allow 2-15 words instead of 2-9
        if len(words) < 2 or len(words) > 15:
            continue
            
        # Exclude table, figure, exercises, etc.
        if any(t.lower().startswith(bad) for bad in BAD_STARTS):
            continue
            
        # Less aggressive BAD_CONTAINS filtering
        if any(bad in t.lower() for bad in BAD_CONTAINS):
            continue
            
        # Don't allow headings ending with ":" (often captions) or "."
        if t.endswith(':') or t.endswith('.'):
            continue
            
        # Additional check: skip if the heading is just the number
        if t.lower() == num.lower():
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
