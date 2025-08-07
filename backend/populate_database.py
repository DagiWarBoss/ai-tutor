import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv
from collections import Counter
import csv

# --- Load Environment Variables ---
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
OUTPUT_CSV_FILE = "extracted_headings_final.csv"

def get_most_common_font_info(doc):
    """Finds the font size and bold status of the main body text."""
    font_counts = Counter()
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        key = (round(s["size"]), "bold" in s["font"].lower())
                        font_counts[key] += 1
    if not font_counts:
        return (10.0, False)
    return font_counts.most_common(1)[0][0]

def find_chapter_number(doc):
    """Automatically finds the chapter number from the first page of the PDF."""
    first_page_text = doc[0].get_text()
    unit_match = re.search(r"UNIT\s+(\d+)", first_page_text, re.IGNORECASE)
    if unit_match:
        return unit_match.group(1)
    code_match = re.search(r"CH(\d{2})", first_page_text)
    if code_match:
        return str(int(code_match.group(1)))
    return None

def extract_headings_hybrid(doc, chapter_number):
    """
    --- The definitive hybrid extraction logic ---
    1. Finds heading starts using font style (bold/larger).
    2. Looks ahead to combine multi-line headings.
    """
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    headings = []
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")
    
    # Extract all lines with metadata first
    all_lines = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    all_lines.append(l)

    i = 0
    while i < len(all_lines):
        line = all_lines[i]
        line_text = "".join(s["text"] for s in line["spans"]).strip()
        match = pat.match(line_text)
        
        if match:
            first_span = line["spans"][0]
            span_size = round(first_span["size"])
            span_is_bold = "bold" in first_span["font"].lower()
            is_heading_start = (span_size > body_font_size) or (span_is_bold and not body_is_bold)

            if is_heading_start:
                num, text = match.group(1).strip(), match.group(2).strip()
                
                # --- Intelligent look-ahead loop ---
                # After finding a heading start, check the next lines for continuations.
                j = i + 1
                while j < len(all_lines):
                    next_line = all_lines[j]
                    next_line_text = "".join(s["text"] for s in next_line["spans"]).strip()
                    
                    # A continuation must not be a new heading itself
                    if pat.match(next_line_text):
                        break
                    
                    # A good continuation is short and starts with a capital letter
                    is_plausible_continuation = (
                        next_line_text
                        and (next_line_text[0].isupper() or next_line_text[0].isdigit())
                        and len(next_line_text.split()) < 7
                    )
                    
                    if is_plausible_continuation:
                        text += " " + next_line_text
                        j += 1 # Consume this line
                    else:
                        break # Stop looking ahead
                
                headings.append((num, ' '.join(text.split())))
                i = j - 1 # Skip the main loop ahead
        i += 1
        
    return headings

if __name__ == '__main__':
    all_headings_data = []

    for root, dirs, files in sorted(os.walk(PDF_ROOT_FOLDER)):
        for filename in sorted(files):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, filename)
                print(f"\nProcessing: {pdf_path}")
                
                try:
                    doc = fitz.open(pdf_path)
                    chapter_num = find_chapter_number(doc)
                    
                    if chapter_num:
                        print(f"  [INFO] Detected Chapter Number: {chapter_num}")
                        final_headings = extract_headings_hybrid(doc, chapter_num)
                        
                        if not final_headings:
                            print("  [INFO] No headings found for this chapter.")
                        else:
                            print(f"  [INFO] Found {len(final_headings)} headings.")
                            for num, text in final_headings:
                                all_headings_data.append({
                                    "source_file": filename,
                                    "topic_number": num,
                                    "extracted_name": text
                                })
                    else:
                        print("  [ERROR] Could not determine chapter number. Skipping.")
                    
                    doc.close()
                except Exception as e:
                    print(f"  [ERROR] Failed to process {filename}: {e}")
    
    if all_headings_data:
        print(f"\n\n=======================================================")
        print(f"Processing complete. Writing {len(all_headings_data)} total headings to {OUTPUT_CSV_FILE}...")
        
        headers = ["source_file", "topic_number", "extracted_name"]
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_headings_data)
            
        print(f"Successfully created {OUTPUT_CSV_FILE}. You can now open it to review.")
        print(f"=======================================================")