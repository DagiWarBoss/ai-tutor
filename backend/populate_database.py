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
    Scans the first page of a PDF to find the chapter number automatically.
    This version is updated to work with different subject codes (CH, PH, MA, etc.).
    """
    first_page_text = doc[0].get_text()
    
    # Looks for patterns like "UNIT 4" (case-insensitive)
    unit_match = re.search(r"UNIT\s+(\d+)", first_page_text, re.IGNORECASE)
    if unit_match:
        return unit_match.group(1)
        
    # --- IMPROVEMENT ---
    # Looks for generic NCERT codes like "CH04", "PH01", "MA12", etc.
    # [A-Z]{2} matches any two capital letters for the subject code.
    code_match = re.search(r"[A-Z]{2}(\d{2})", first_page_text)
    if code_match:
        # Converts "04" to "4"
        return str(int(code_match.group(1)))

    return None

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

    # The os.walk function will automatically go through all subjects and classes
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