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
    x: float
    size: float
    bold: bool

# ---------------- CSV helpers ----------------
def load_csv_for_chapter(csv_path: str, subject: str, class_: str, chapter_file: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    if not os.path.exists(csv_path):
        log(f"[ERROR] CSV not found: {csv_path}")
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["subject"] == subject and r["class"] == class_ and r["chapter_file"] == chapter_file:
                hn = (r["heading_number"] or "").strip().strip(".")
                ht = r.get("heading_text", "")
                if hn and ht:
                    rows.append((hn, ht))
    rows.sort(key=lambda t: [int(x) for x in t[0].split(".") if x.isdigit()])
    log(f"[CSV] Loaded {len(rows)} headings for {subject} | {class_} | {chapter_file}")
    return rows

def build_children_by_parent(csv_list: List[Tuple[str, str]]) -> Dict[str, List[Tuple[str, str]]]:
    by_parent: Dict[str, List[Tuple[str, str]]] = {}
    for n, t in csv_list:
        parts = n.split(".")
        if len(parts) >= 2:
            parent = ".".join(parts[:-1]).strip(".")
            if parent:
                by_parent.setdefault(parent, []).append((n, t))
    for k in by_parent:
        by_parent[k].sort(key=lambda t: [int(x) for x in t[0].split(".") if x.isdigit()])
    return by_parent

# ---------------- DB helpers ----------------
def connect_db():
    log("[INFO] Connecting to Supabase/Postgres...")
    conn = psycopg2.connect(SUPABASE_URI)
    conn.autocommit = False
    return conn, conn.cursor()

def fetch_chapter(cursor, subject_name: str, class_number: str, chapter_name: str):
    cursor.execute("SELECT id FROM subjects WHERE name = %s", (subject_name,))
    s = cursor.fetchone()
    if not s: return None, None
    subject_id = s[0]
    cursor.execute("SELECT id FROM chapters WHERE name = %s AND class_number = %s AND subject_id = %s",
                   (chapter_name, class_number, subject_id))
    ch = cursor.fetchone()
    return subject_id, ch

def fetch_db_topic_numbers(cursor, chapter_id: int) -> Set[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s", (chapter_id,))
    return {r[0] for r in cursor.fetchall()}

def update_topic_text(cursor, chapter_id: int, topic_number: str, content: str) -> int:
    cursor.execute(
        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
        (content, chapter_id, topic_number),
    )
    return cursor.rowcount

# ---------------- text-layer extractor ----------------
def get_body_font(doc) -> Tuple[float, bool]:
    font_counts = Counter()
    for page_idx, page in enumerate(doc):
        if page_idx > 10: break
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 10))
                    font = span.get("font", "").lower()
                    key = (size, "bold" in font)
                    font_counts[key] += len(span.get("text", ""))
    if not font_counts: return 10.0, False
    (size, bold), _ = font_counts.most_common(1)[0]
    return float(size), bool(bold)

def extract_numbered_headings_by_layout(doc, body_size: float, body_bold: bool) -> List[HeadingAnchor]:
    anchors: List[HeadingAnchor] = []
    for page_idx, page in enumerate(doc):
        pdata = page.get_text("dict")
        for block in pdata.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans: continue
                text = "".join(s.get("text", "") for s in spans).strip()
                m = HEADING_NUMBER_RE.match(text)
                if not m: continue
                first_span = spans[0]
                size = float(first_span.get("size", 10.0))
                font = first_span.get("font", "").lower()
                bold = "bold" in font
                x0, y0, _, _ = line.get("bbox", [0, 0, 0, 0])
                title = (m.group(2) or "").strip()
                is_heading = (x0 < 90) and ((size >= body_size + 1.0) or (bold and not body_bold))
                if is_heading:
                    number = m.group(1).strip(". ")
                    anchors.append(HeadingAnchor(number=number, title=title, page=page_idx, y=float(y0), x=float(x0), size=size, bold=bold))
    return anchors

def dedupe_and_sort(anchors: List[HeadingAnchor]) -> List[HeadingAnchor]:
    seen, uniq = set(), []
    for a in anchors:
        key = (a.number, a.page, round(a.y, 1))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    uniq.sort(key=lambda h: (h.page, h.y))
    return uniq

def collect_blocks(doc) -> List[Dict]:
    blocks_all = []
    for page_idx, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            text = (b[4] or "").strip().replace("\n", " ")
            if text:
                blocks_all.append({"page": page_idx, "x": b[0], "y": b[1], "text": text})
    return blocks_all

def segment_between_anchors(blocks: List[Dict], anchors: List[HeadingAnchor]) -> Dict[str, str]:
    topic_text: Dict[str, str] = {}
    heading_texts = {a.title for a in anchors}

    for i, a in enumerate(anchors):
        start_page, start_y = a.page, a.y
        end_page, end_y = (anchors[i + 1].page, anchors[i + 1].y) if i + 1 < len(anchors) else (float("inf"), float("inf"))
        
        chunks = []
        for blk in blocks:
            after = blk["page"] > start_page or (blk["page"] == start_page and blk["y"] > start_y)
            before = blk["page"] < end_page or (blk["page"] == end_page and blk["y"] < end_y)
            if after and before:
                # Check if the block text is another heading's title
                if blk["text"] in heading_texts: continue
                chunks.append(blk["text"])
        
        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
    return topic_text

def extract_textlayer_topics(doc) -> Tuple[Dict[str, str], List[HeadingAnchor]]:
    body_size, body_bold = get_body_font(doc)
    anchors = extract_numbered_headings_by_layout(doc, body_size, body_bold)
    anchors = dedupe_and_sort(anchors)
    if not anchors: return {}, []
    
    blocks = collect_blocks(doc)
    topic_map = segment_between_anchors(blocks, anchors)
    return topic_map, anchors

# ---------------- OCR fallback ----------------
def _norm_txt(s: str) -> str:
    s = (s or "").replace("’","'").replace("“",'"').replace("”",'"').replace("–","-")
    return SPACE_RE.sub(" ", s.strip()).lower()

def hocr_to_lines(hocr_html: str, page_index: int) -> List[Dict]:
    # --- FIX: Using the recommended XML parser ---
    soup = BeautifulSoup(hocr_html, "xml")
    lines = []
    for line in soup.find_all(class_="ocr_line"):
        title = line.get("title", "")
        m = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
        if not m: continue
        x0, y0, x1, y1 = map(int, m.groups())
        words = [w.get_text(strip=True) for w in line.find_all(class_="ocrx_word")]
        text = SPACE_RE.sub(" ", " ".join(words).strip())
        if text:
            lines.append({"page": page_index, "x": x0, "y": y0, "text": text})
    lines.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return lines

# ... (Other OCR and span-slicing functions would go here, but keeping it simpler for now) ...

# ---------------- 'Search and Rescue' function ----------------
def find_missing_by_text_search(missing_specs: List[Tuple[str, str]], all_blocks: List[Dict]) -> List[HeadingAnchor]:
    """Pass 4: Tries to find missing headings by searching for their titles in the raw text."""
    found_anchors: List[HeadingAnchor] = []
    
    for spec_num, spec_title in missing_specs:
        if not spec_title or len(spec_title) < 5: continue
        
        norm_title = _norm_txt(spec_title)
        
        for i, block in enumerate(all_blocks):
            if norm_title in _norm_txt(block['text']):
                found_anchors.append(HeadingAnchor(number=spec_num, title=spec_title, page=block['page'], y=block['y'], x=block['x'], size=0, bold=False))
                break 
                
    log(f"[P4][SEARCH] Rescued {len(found_anchors)} anchors by text search.")
    return found_anchors

# ---------------- main ----------------
def main():
    log("[BOOT] Fill single chapter (2-Pass: Text-layer -> Search)")
    
    chapter_file = f"{TARGET_CHAPTER}.pdf"
    pdf_path = os.path.join(PDF_ROOT_FOLDER, TARGET_SUBJECT, TARGET_CLASS, chapter_file)
    log(f"[INFO] Target: {TARGET_SUBJECT} | {TARGET_CLASS} | {TARGET_CHAPTER}")
    if not os.path.exists(pdf_path):
        log("[ERROR] PDF not found.")
        return

    csv_list = load_csv_for_chapter(CSV_PATH, TARGET_SUBJECT, TARGET_CLASS, chapter_file)
    if not csv_list: return

    try:
        conn, cursor = connect_db()
        _, chapter_row = fetch_chapter(cursor, TARGET_SUBJECT, TARGET_CLASS, TARGET_CHAPTER)
        if not chapter_row:
            log("[ERROR] Chapter row not found in DB.")
            return
        chapter_id = chapter_row[0]
        log(f"[INFO] DB chapter_id: {chapter_id}")
    except Exception as e:
        log(f"[ERROR] DB setup failed: {e}")
        return

    # Pass 1: text-layer extraction
    doc = fitz.open(pdf_path)
    topic_map, anchors = extract_textlayer_topics(doc)
    log(f"[P1] Text-layer extracted: {len(topic_map)} topics")
    
    updated_count = 0
    updated_topic_numbers = set()

    for num, content in topic_map.items():
        if content and len(content.strip()) > 20:
            if update_topic_text(cursor, chapter_id, num, content) > 0:
                updated_count += 1
                updated_topic_numbers.add(num)
    
    conn.commit()
    log(f"[P1] Updates committed: {updated_count}")
    
    # Pass 4 (simplified from Pass 4): Search and Rescue
    csv_topic_numbers = {num for num, _ in csv_list}
    still_missing_nums = csv_topic_numbers - updated_topic_numbers
    
    if still_missing_nums:
        log(f"[P4][SEARCH] Attempting to rescue {len(still_missing_nums)} missing topics by text search...")
        missing_specs = [(num, title) for num, title in csv_list if num in still_missing_nums]
        all_blocks = collect_blocks(doc)
        
        rescued_anchors = find_missing_by_text_search(missing_specs, all_blocks)
        
        if rescued_anchors:
            # Combine original and rescued anchors and re-segment the whole document
            final_anchors = dedupe_and_sort(anchors + rescued_anchors)
            log(f"[P4] Re-segmenting with {len(final_anchors)} total anchors...")
            final_map = segment_between_anchors(all_blocks, final_anchors)
            
            rescued_updates = 0
            for num, content in final_map.items():
                if num in still_missing_nums and content and len(content.strip()) > 20:
                    if update_topic_text(cursor, chapter_id, num, content) > 0:
                        rescued_updates += 1
            
            if rescued_updates > 0:
                conn.commit()
                log(f"[P4] Search-and-rescue updates committed: {rescued_updates}")

    doc.close()
    cursor.close()
    conn.close()
    log("[DONE] Chapter fill complete.")

if __name__ == "__main__":
    main()