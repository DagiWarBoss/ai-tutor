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
OUTPUT_CSV_FILE = "extracted_headings_all_subjects.csv"

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
    """
    --- UPGRADED FUNCTION ---
    Scans the first 3 pages of a PDF to find the chapter number using multiple patterns.
    """
    # Search the first 3 pages of the document
    for page_num in range(min(3, doc.page_count)):
        page_text = doc[page_num].get_text()
        
        # Pattern 1: "CHAPTER X" (Most reliable for many books)
        chapter_match = re.search(r"CHAPTER\s+(\d{1,2})", page_text, re.IGNORECASE)
        if chapter_match:
            return chapter_match.group(1)

        # Pattern 2: "UNIT X"
        unit_match = re.search(r"UNIT\s+(\d+)", page_text, re.IGNORECASE)
        if unit_match:
            return unit_match.group(1)
        
        # Pattern 3: NCERT codes like "CH04", "PH01", "MA12"
        code_match = re.search(r"[A-Z]{2}(\d{2})", page_text)
        if code_match:
            return str(int(code_match.group(1))) # Converts "04" to "4"
            
    return None # Return None if no pattern is matched in the first 3 pages

def extract_headings_by_style(doc, chapter_number):
    """
    Extracts headings by identifying text that is either larger or bolder than the body text.
    """
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    headings = []
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+(.*)$")

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    match = pat.match(line_text)
                    
                    if match:
                        first_span = l["spans"][0]
                        span_size = round(first_span["size"])
                        span_is_bold = "bold" in first_span["font"].lower()

                        is_heading = (span_size > body_font_size) or (span_is_bold and not body_is_bold)

                        if is_heading:
                            num, text = match.group(1).strip(), match.group(2).strip()
                            clean_text = ' '.join(text.split())
                            headings.append((num, clean_text))
    return headings

if __name__ == '__main__':
    all_headings_data = []

    for root, dirs, files in sorted(os.walk(PDF_ROOT_FOLDER)):
        for filename in sorted(files):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, filename)
                print(f"\n\n=======================================================")
                print(f"Processing File: {filename}")
                
                try:
                    doc = fitz.open(pdf_path)
                    chapter_num = find_chapter_number(doc)
                    
                    if chapter_num:
                        print(f"  [INFO] Detected Chapter Number: {chapter_num}")
                        final_headings = extract_headings_by_style(doc, chapter_num)
                        
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