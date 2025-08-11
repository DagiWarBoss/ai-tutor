import os
import re
import csv
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Set

import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv
from PIL import Image
import pytesseract
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

# Ignore the XML parsed as HTML warning, as we are now handling it.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

try:
    from rapidfuzz import fuzz
    HAVE_FUZZ = True
except ImportError:
    HAVE_FUZZ = False

# ---------------- Config ----------------
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"

TARGET_SUBJECT = "Chemistry"
TARGET_CLASS = "Class 11"
TARGET_CHAPTER = "Some Basic Concepts Of Chemistry"

# OCR fallback thresholds
OCR_MIN_HEADINGS_THRESHOLD = 8
OCR_CHILD_MIN_FOUND = 2
OCR_ZOOM = 4.0
OCR_LANG = "eng"
OCR_FUZZY_THRESHOLD = 85

# If Tesseract not on PATH, set full path
TESSERACT_EXE = None  # e.g., r"C:\Program Files\Tesseract-OCR\tesseract.exe"

HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,5})\b[^\w]*(.*)$")
SPACE_RE = re.compile(r"\s+")

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

def log(msg: str):
    print(msg, flush=True)

@dataclass
class HeadingAnchor:
    number: str
    title: str
    page: int
    y: float
    # ... (other fields as needed) ...

# ... [All other helper functions from the advanced script remain the same] ...
# ... load_csv_for_chapter, build_children_by_parent, connect_db, etc. ...
# ... The only change is in hocr_to_lines and a new function + main logic ...

def hocr_to_lines(hocr_html: str, page_index: int) -> List[Dict]:
    # --- FIX: Using the recommended XML parser ---
    soup = BeautifulSoup(hocr_html, "xml")
    lines = []
    # ... (rest of the function is the same) ...
    for line in soup.find_all(class_="ocr_line"):
        title = line.get("title", "")
        m = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
        if not m: continue
        x0, y0, x1, y1 = map(int, m.groups())
        words = [w.get_text(strip=True) for w in line.find_all(class_="ocrx_word")]
        text = SPACE_RE.sub(" ", " ".join(words).strip())
        if not text: continue
        lines.append({"page": page_index, "x": x0, "y": y0, "x1": x1, "y1": y1, "text": text})
    lines.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return lines

def find_missing_by_text_search(missing_specs: List[Tuple[str, str]], all_blocks: List[Dict]) -> Dict[str, str]:
    """
    --- NEW 'SEARCH AND RESCUE' FUNCTION ---
    Pass 4: Tries to find missing headings by searching for their titles in the raw text.
    """
    rescued_topics: Dict[str, str] = {}
    
    # Create a searchable list of block texts
    block_texts = [b['text'] for b in all_blocks]
    
    # Create a list of anchors from the found blocks
    found_anchors: List[HeadingAnchor] = []
    for spec_num, spec_title in missing_specs:
        if not spec_title: continue
        # Find the first block that contains the title text
        for i, block_text in enumerate(block_texts):
            if _norm_txt(spec_title) in _norm_txt(block_text):
                block = all_blocks[i]
                found_anchors.append(HeadingAnchor(number=spec_num, title=spec_title, page=block['page'], y=block['y']))
                break # Move to next missing spec once found
                
    if not found_anchors:
        return {}
        
    log(f"[P4][SEARCH] Rescued {len(found_anchors)} anchors by text search.")
    
    # Segment the text based on these newly found anchors
    rescued_topics = segment_between_anchors(all_blocks, found_anchors)
    return rescued_topics


# ... [All other functions from the advanced script should be here] ...
# For brevity, I'll just show the updated main() function. You should use the
# full script I provided before, but replace hocr_to_lines and add the function above.

def main():
    # ... (all setup from the previous advanced script) ...
    log("[BOOT] Fill single chapter (4-Pass: Text-layer -> Slicing -> OCR -> Search)")
    
    # ... (load CSV, connect DB, fetch chapter, etc.) ...

    # Pass 1 & 2 & 3 (Text-layer, Slicing, OCR)
    # ... (This part of the main function remains the same, it will run all
    #      three passes and produce the 'updated_topic_numbers' set) ...

    # --- NEW: PASS 4 - SEARCH AND RESCUE ---
    db_set_after_ocr = fetch_db_topic_numbers(cursor, chapter_id)
    still_missing_nums = db_set_after_ocr - updated_topic_numbers
    
    if still_missing_nums:
        log(f"[P4][SEARCH] Attempting to rescue {len(still_missing_nums)} missing topics by text search...")
        
        # Create a list of specifications for the missing topics from the CSV
        missing_specs = [(num, title) for num, title in csv_list if num in still_missing_nums]
        
        # Collect all text blocks if not already done
        all_blocks = collect_blocks(doc)
        
        rescued_map = find_missing_by_text_search(missing_specs, all_blocks)
        
        search_updates = 0
        for num, content in rescued_map.items():
            if not content or len(content.strip()) < 20: continue
            try:
                rowcount = update_topic_text(cursor, chapter_id, num, content)
                if rowcount > 0:
                    search_updates += 1
                    updated_topic_numbers.add(num)
                    log(f"[P4][SEARCH] Rescued and updated {num} (len={len(content)})")
            except Exception as e:
                log(f"[P4][ERROR] Update {num}: {e}")
        
        if search_updates > 0:
            conn.commit()
            log(f"[P4] Search-and-rescue updates written: {search_updates}")

    # ... (Final missing list report and closing connections) ...