import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv
from collections import Counter

# --- Load Environment Variables ---
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Change per chapter

def get_most_common_font_size(doc):
    """
    Scans the document to find the most common font size, likely the body text.
    """
    font_sizes = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        font_sizes.append(round(s["size"]))
    
    if not font_sizes:
        return 10.0 # Return a default body size if none found

    # Find the most common font size (the mode)
    return Counter(font_sizes).most_common(1)[0][0]


def extract_headings_by_font(pdf_path, chapter_number):
    """
    Extracts headings by identifying text with a larger font size than the body.
    This is a much more reliable method than the previous line-based logic.
    """
    doc = fitz.open(pdf_path)
    
    # 1. Determine the font size of the main body text
    body_font_size = get_most_common_font_size(doc)
    print(f"--- [INFO] Determined main body font size to be ~{body_font_size} ---")

    headings = []
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    # 2. Iterate through the document's text blocks
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    # Combine all text spans in a line to get the full line text
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    
                    # Check if this line matches our heading number pattern
                    match = pat.match(line_text)
                    if match:
                        # Get the font size of the first part of the line
                        span_font_size = round(l["spans"][0]["size"])

                        # 3. A heading must have a font size larger than the body text
                        if span_font_size > body_font_size:
                            num, text = match.group(1).strip(), match.group(2).strip()
                            # Clean up any residual newlines or extra spaces
                            clean_text = ' '.join(text.split())
                            headings.append((num, clean_text))

    doc.close()
    return headings


if __name__ == '__main__':
    try:
        pdf_path = os.path.join(
            script_dir, PDF_ROOT_FOLDER,
            "Chemistry", "Class 11", TARGET_CHAPTER
        )
        # Call the new, more reliable function
        final_headings = extract_headings_by_font(pdf_path, CHAPTER_NUMBER)
        
        print(f"\n--- FINAL RESULTS ---")
        print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
        if not final_headings:
            print("  - No headings found.")
        else:
            for num, text in final_headings:
                print(f"  - {num} {text}")
        
        print(f"\nTotal final matches: {len(final_headings)}")

    except FileNotFoundError:
        print(f"Error: The file was not found at the specified path: {pdf_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")