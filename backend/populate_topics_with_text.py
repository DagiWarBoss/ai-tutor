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
from bs4 import BeautifulSoup

try:
    from rapidfuzz import fuzz
    HAVE_FUZZ = True
except Exception:
    HAVE_FUZZ = False

# ---------------- Config ----------------
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"

TARGET_SUBJECT = "Chemistry"
TARGET_CLASS = "Class 11"
TARGET_CHAPTER = "Some Basic Concepts Of Chemistry"

# OCR fallback thresholds
OCR_MIN_HEADINGS_THRESHOLD = 8          # if fewer than this from text-layer
OCR_CHILD_MIN_FOUND = 2                 # if child slicing finds fewer than this, consider OCR
OCR_ZOOM = 4.0                          # ~288dpi
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
                ht = r.get("heading_text", None)
                if hn:
                    rows.append((hn, ht))
    rows.sort(key=lambda t: [int(x) for x in t[0].split(".") if x.isdigit()])
    log(f"[CSV] Loaded {len(rows)} headings for {subject} | {class_} | {chapter_file}")
    return rows


def build_children_by_parent(csv_list: List[Tuple[str, Optional[str]]]) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    by_parent: Dict[str, List[Tuple[str, Optional[str]]]] = {}
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
    if not s:
        return None, None
    subject_id = s[0]
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters WHERE name = %s AND class_number = %s AND subject_id = %s",
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


def diagnose_topic_numbers(cursor, chapter_id: int):
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s ORDER BY topic_number", (chapter_id,))
    nums = [r[0] for r in cursor.fetchall()]
    log(f"[DIAG] DB topic_numbers: {nums}")


# ---------------- text-layer extractor ----------------
def get_body_font(doc) -> Tuple[float, bool]:
    font_counts = Counter()
    for page_idx, page in enumerate(doc):
        if page_idx > 10:
            break
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 10))
                    font = span.get("font", "").lower()
                    key = (size, "bold" in font)
                    font_counts[key] += len(span.get("text", ""))
    if not font_counts:
        return 10.0, False
    (size, bold), _ = font_counts.most_common(1)[0]
    return float(size), bool(bold)


def read_toc(doc):
    try:
        return doc.get_toc(simple=True) or []
    except Exception:
        return []


def toc_to_anchors(toc) -> List[HeadingAnchor]:
    anchors = []
    for level, title, page1 in toc:
        if not isinstance(title, str):
            continue
        m = HEADING_NUMBER_RE.match(title)
        if not m:
            continue
        page_idx = max(0, page1 - 1)
        number = m.group(1).strip(". ")
        title_text = (m.group(2) or "").strip()
        anchors.append(HeadingAnchor(number=number, title=title_text, page=page_idx, y=0.0, x=0.0, size=12.0, bold=False))
    return anchors


def extract_numbered_headings_by_layout(doc, body_size: float, body_bold: bool) -> List[HeadingAnchor]:
    anchors: List[HeadingAnchor] = []
    for page_idx, page in enumerate(doc):
        pdata = page.get_text("dict")
        for block in pdata.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                m = HEADING_NUMBER_RE.match(text)
                if not m:
                    continue
                first_span = spans[0]
                size = float(first_span.get("size", 10.0))
                font = first_span.get("font", "").lower()
                bold = "bold" in font
                x0, y0, x1, y1 = line.get("bbox", [0, 0, 0, 0])
                title = (m.group(2) or "").strip()
                is_heading = (x0 < 90) and ((size >= body_size + 1.0) or (bold and not body_bold))
                if is_heading:
                    number = m.group(1).strip(". ")
                    anchors.append(HeadingAnchor(number=number, title=title, page=page_idx, y=float(y0), x=float(x0), size=size, bold=bold))
    return anchors


def dedupe_and_sort(anchors: List[HeadingAnchor]) -> List[HeadingAnchor]:
    seen = set()
    uniq = []
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
            try:
                x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            except Exception:
                text = b[4] if len(b) > 4 else ""
                x0, y0 = b[0], b[1]
            text = (text or "").strip().replace("\n", " ")
            if not text:
                continue
            blocks_all.append({"page": page_idx, "x": x0, "y": y0, "text": text})
    return blocks_all


def segment_between_anchors(blocks: List[Dict], anchors: List[HeadingAnchor]) -> Dict[str, str]:
    topic_text: Dict[str, str] = {}
    heading_numbers = [a.number for a in anchors]

    def is_heading_line(text: str) -> bool:
        return any(text.startswith(num) for num in heading_numbers)

    for i, a in enumerate(anchors):
        start_page, start_y = a.page, a.y
        if i + 1 < len(anchors):
            b = anchors[i + 1]
            end_page, end_y = b.page, b.y
        else:
            end_page, end_y = float("inf"), float("inf")
        chunks = []
        for blk in blocks:
            after = blk["page"] > start_page or (blk["page"] == start_page and blk["y"] > start_y)
            before = blk["page"] < end_page or (blk["page"] == end_page and blk["y"] < end_y)
            if after and before:
                if is_heading_line(blk["text"]):
                    continue
                chunks.append(blk["text"])
        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
    return topic_text


def extract_textlayer_topics(pdf_path: str) -> Tuple[Dict[str, str], List[HeadingAnchor]]:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log(f"[ERROR] Open PDF failed: {e}")
        return {}, []
    toc = read_toc(doc)
    anchors: List[HeadingAnchor] = []
    if toc:
        anchors = toc_to_anchors(toc)
        if len(anchors) < 2:
            anchors = []
    if not anchors:
        body_size, body_bold = get_body_font(doc)
        anchors = extract_numbered_headings_by_layout(doc, body_size, body_bold)
    anchors = dedupe_and_sort(anchors)
    if not anchors:
        doc.close()
        return {}, []
    blocks = collect_blocks(doc)
    doc.close()
    topic_map = segment_between_anchors(blocks, anchors)
    return topic_map, anchors


# ---------------- span-based child slicing ----------------
def _norm_txt(s: str) -> str:
    s = (s or "")
    s = s.replace("’","'").replace("‘","'").replace("“",'"').replace("”",'"')
    s = s.replace("–","-").replace("—","-").replace("·",".").replace("•"," ")
    return SPACE_RE.sub(" ", s.strip()).lower()


def span_lines_for_doc(pdf_path: str) -> List[Dict]:
    doc = fitz.open(pdf_path)
    lines = []
    for page_idx, page in enumerate(doc):
        pdata = page.get_text("dict")
        for block in pdata.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line.get("spans", [])
                if not spans:
                    continue
                x0, y0, x1, y1 = line.get("bbox", [0,0,0,0])
                text = "".join(s.get("text","") for s in spans).strip()
                if not text:
                    continue
                first = spans[0]
                font = (first.get("font","") or "").lower()
                bold = "bold" in font
                lines.append({"page": page_idx, "x": x0, "y": y0, "text": text, "bold": bold})
    doc.close()
    lines.sort(key=lambda r: (r["page"], r["y"]))
    return lines


def split_children_in_parent_window(window_lines: List[Dict], children_specs: List[Tuple[str, Optional[str]]], left_margin=95, min_title_len=5) -> Dict[str, str]:
    cands = [ln for ln in window_lines if ln["bold"] and ln["x"] < left_margin]
    found = []
    for cnum, ctitle in children_specs:
        if not cnum or not ctitle:
            continue
        tnorm = _norm_txt(ctitle)
        if len(tnorm) < min_title_len:
            continue
        best = None
        for ln in cands:
            if tnorm in _norm_txt(ln["text"]):
                best = ln
                break
        if best is None:
            half = tnorm[: max(5, len(tnorm)//2)]
            for ln in cands:
                if _norm_txt(ln["text"]).startswith(half):
                    best = ln
                    break
        if best:
            found.append({"number": cnum.strip("."), "page": best["page"], "y": best["y"]})
    if not found:
        return {}
    found.sort(key=lambda a: (a["page"], a["y"]))
    out: Dict[str, str] = {}
    for i, a in enumerate(found):
        end = found[i+1] if i+1 < len(found) else None
        chunks = []
        for ln in window_lines:
            after = (ln["page"] > a["page"]) or (ln["page"] == a["page"] and ln["y"] > a["y"])
            before = True
            if end:
                before = (ln["page"] < end["page"]) or (ln["page"] == end["page"] and ln["y"] < end["y"])
            if after and before:
                if ln["page"] == a["page"] and abs(ln["y"] - a["y"]) < 2:
                    continue
                chunks.append(ln["text"])
        merged = SPACE_RE.sub(" ", "\n".join(chunks).strip())
        if merged and len(merged) >= 20:
            out[a["number"]] = merged
    return out


# ---------------- OCR fallback ----------------
def ocr_render_pages(pdf_path: str, zoom: float) -> List[Tuple[int, Image.Image]]:
    doc = fitz.open(pdf_path)
    images = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append((i, img))
    doc.close()
    return images


def ocr_page_hocr(pil_image: Image.Image, lang: str) -> str:
    out = pytesseract.image_to_pdf_or_hocr(pil_image, extension="hocr", lang=lang)
    return out.decode("utf-8", errors="ignore") if isinstance(out, (bytes, bytearray)) else str(out)


def hocr_to_lines(hocr_html: str, page_index: int) -> List[Dict]:
    soup = BeautifulSoup(hocr_html, "lxml")
    lines = []
    for line in soup.find_all(class_="ocr_line"):
        title = line.get("title", "")
        m = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
        if not m:
            continue
        x0, y0, x1, y1 = map(int, m.groups())
        words = [w.get_text(strip=True) for w in line.find_all(class_="ocrx_word")]
        text = SPACE_RE.sub(" ", " ".join(words).strip())
        if not text:
            continue
        lines.append({"page": page_index, "x": x0, "y": y0, "x1": x1, "y1": y1, "text": text})
    lines.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return lines


def ocr_detect_numbered_parents(lines: List[Dict], left_margin_px: int = 260) -> List[Dict]:
    anchors = []
    for ln in lines:
        m = HEADING_NUMBER_RE.match(ln["text"])
        if not m:
            continue
        if ln["x"] > left_margin_px:
            continue
        number = m.group(1).strip(".")
        anchors.append({"type": "numbered", "number": number, "page": ln["page"], "y": ln["y"], "text": ln["text"]})
    anchors.sort(key=lambda a: (a["page"], a["y"]))
    uniq, seen = [], set()
    for a in anchors:
        key = (a["number"], a["page"], int(a["y"]/2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def ocr_best_child_matches_in_window(window_lines: List[Dict], csv_children: List[Tuple[str, Optional[str]]], left_margin_px: int = 300, fuzzy_threshold: int = 85) -> List[Dict]:
    cands = [ln for ln in window_lines if ln["x"] <= left_margin_px]
    results = []
    for child_num, child_title in csv_children:
        if not child_num or not child_title:
            continue
        target = _norm_txt(child_title)
        best, best_score = None, -1
        for ln in cands:
            cand_norm = _norm_txt(ln["text"])
            if HAVE_FUZZ:
                score = fuzz.partial_ratio(target, cand_norm)
            else:
                score = 100 if target in cand_norm else (90 if cand_norm.startswith(target[: max(5, len(target)//2)]) else 0)
            if score > best_score:
                best_score = score
                best = ln
        if best and best_score >= fuzzy_threshold:
            results.append({"type": "csv_child", "number": child_num.strip("."), "page": best["page"], "y": best["y"], "text": best["text"], "score": best_score})
    results.sort(key=lambda a: (a["page"], a["y"]))
    uniq, seen = [], set()
    for a in results:
        key = (a["number"], a["page"], int(a["y"]/2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def ocr_segment_window(lines_sorted: List[Dict], start_anchor: Dict, end_anchor: Optional[Dict], inner_anchors: List[Dict]) -> Dict[str, str]:
    anchors = inner_anchors[:]
    anchors.sort(key=lambda a: (a["page"], a["y"]))
    segments: Dict[str, str] = {}

    def in_range(ln, s, e):
        after = (ln["page"] > s["page"]) or (ln["page"] == s["page"] and ln["y"] > s["y"])
        before = True
        if e:
            before = (ln["page"] < e["page"]) or (ln["page"] == e["page"] and ln["y"] < e["y"])
        return after and before

    if anchors:
        for i, a in enumerate(anchors):
            start = a
            end = anchors[i + 1] if i + 1 < len(anchors) else end_anchor
            chunks = []
            for ln in lines_sorted:
                if not in_range(ln, start, end):
                    continue
                if (ln["page"] == start["page"] and abs(ln["y"] - start["y"]) < 3):
                    continue
                if end and (ln["page"] == end["page"] and abs(ln["y"] - end["y"]) < 3):
                    continue
                chunks.append(ln["text"])
            merged = SPACE_RE.sub(" ", "\n".join(chunks).strip())
            if merged:
                segments[a["number"]] = merged
    else:
        chunks = []
        for ln in lines_sorted:
            if not in_range(ln, start_anchor, end_anchor):
                continue
            if (ln["page"] == start_anchor["page"] and abs(ln["y"] - start_anchor["y"]) < 3):
                continue
            if end_anchor and (ln["page"] == end_anchor["page"] and abs(ln["y"] - end_anchor["y"]) < 3):
                continue
            chunks.append(ln["text"])
        merged = SPACE_RE.sub(" ", "\n".join(chunks).strip())
        if merged:
            segments[start_anchor["number"]] = merged
    return segments


def ocr_extract_topics(pdf_path: str, csv_children_map: Optional[Dict[str, List[Tuple[str, Optional[str]]]]], tesseract_bin: Optional[str], lang: str, zoom: float, fuzzy_threshold: int) -> Dict[str, str]:
    if tesseract_bin:
        pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    images = ocr_render_pages(pdf_path, zoom=zoom)
    all_lines: List[Dict] = []
    for page_index, img in images:
        try:
            hocr = ocr_page_hocr(img, lang=lang)
            lines = hocr_to_lines(hocr, page_index)
            all_lines.extend(lines)
        except Exception:
            continue
    if not all_lines:
        return {}
    parents = ocr_detect_numbered_parents(all_lines)
    if not parents:
        return {}
    lines_sorted = sorted(all_lines, key=lambda r: (r["page"], r["y"], r["x"]))
    segments: Dict[str, str] = {}
    for i, parent in enumerate(parents):
        end_parent = parents[i + 1] if i + 1 < len(parents) else None
        window_lines = []
        for ln in lines_sorted:
            after = (ln["page"] > parent["page"]) or (ln["page"] == parent["page"] and ln["y"] > parent["y"])
            before = True
            if end_parent:
                before = (ln["page"] < end_parent["page"]) or (ln["page"] == end_parent["page"] and ln["y"] < end_parent["y"])
            if after and before:
                window_lines.append(ln)
        child_specs = csv_children_map.get(parent["number"], []) if csv_children_map else []
        child_anchors = []
        if child_specs:
            child_anchors = ocr_best_child_matches_in_window(window_lines, child_specs, left_margin_px=300, fuzzy_threshold=fuzzy_threshold)
        segs = ocr_segment_window(lines_sorted, parent, end_parent, child_anchors)
        segments.update(segs)
    return segments


# ---------------- main ----------------
def main():
    log("[BOOT] Fill single chapter (text-layer -> span-slicing -> OCR fallback)")
    if TESSERACT_EXE:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

    chapter_file = f"{TARGET_CHAPTER}.pdf"
    pdf_path = os.path.join(PDF_ROOT_FOLDER, TARGET_SUBJECT, TARGET_CLASS, chapter_file)
    log(f"[INFO] Target: {TARGET_SUBJECT} | {TARGET_CLASS} | {TARGET_CHAPTER}")
    log(f"[INFO] PDF path: {pdf_path}")

    if not os.path.exists(pdf_path):
        log("[ERROR] PDF not found.")
        return

    # Load CSV for chapter
    csv_list = load_csv_for_chapter(CSV_PATH, TARGET_SUBJECT, TARGET_CLASS, chapter_file)
    children_map = build_children_by_parent(csv_list)

    # DB connect and chapter resolve
    try:
        conn, cursor = connect_db()
    except Exception as e:
        log(f"[ERROR] DB connect failed: {e}")
        return

    try:
        subject_id, chapter_row = fetch_chapter(cursor, TARGET_SUBJECT, TARGET_CLASS, TARGET_CHAPTER)
        if not chapter_row:
            log("[ERROR] Chapter row not found in DB.")
            cursor.close(); conn.close()
            return
        chapter_id = chapter_row[0]
        log(f"[INFO] DB chapter_id: {chapter_id}")
    except Exception as e:
        log(f"[ERROR] Load chapter failed: {e}")
        cursor.close(); conn.close()
        return

    # DB key set
    try:
        db_set = fetch_db_topic_numbers(cursor, chapter_id)
        log(f"[INFO] DB has {len(db_set)} topics for this chapter.")
    except Exception as e:
        log(f"[ERROR] Fetch DB topics failed: {e}")
        cursor.close(); conn.close()
        return

    # Pass 1: text-layer extraction
    topic_map, anchors = extract_textlayer_topics(pdf_path)
    log(f"[P1] Text-layer extracted: {len(topic_map)} topics | anchors={len(anchors)}")

    updated_topic_numbers: Set[str] = set()
    updated = 0

    # Write parents from pass 1
    for num, content in topic_map.items():
        if not content or len(content.strip()) < 20:
            continue
        try:
            rowcount = update_topic_text(cursor, chapter_id, num.strip().strip("."), content)
            if rowcount > 0:
                updated += 1
                updated_topic_numbers.add(num.strip().strip("."))
            else:
                # Log diagnostic once per number
                log(f"[P1][MISS] No row for topic_number='{num}'.")
        except Exception as e:
            log(f"[P1][ERROR] Update parent {num}: {e}")

    if updated:
        try:
            conn.commit()
        except Exception as e:
            log(f"[P1][ERROR] commit: {e}")
            conn.rollback()
    log(f"[P1] Parent updates written: {updated}")

    # Pass 2: span-based child slicing
    child_updates = 0
    if anchors:
        parent_pts = [(a.number.strip("."), a.page, a.y) for a in anchors]
        parent_pts.sort(key=lambda t: (t[1], t[2]))
        all_lines = span_lines_for_doc(pdf_path)
        for idx, (pnum, ppage, py) in enumerate(parent_pts):
            child_specs = children_map.get(pnum, [])
            if not child_specs:
                continue
            if pnum not in updated_topic_numbers:
                continue
            if idx + 1 < len(parent_pts):
                _, n_ppage, n_py = parent_pts[idx+1]
            else:
                n_ppage, n_py = None, None
            window_lines = []
            for ln in all_lines:
                after = (ln["page"] > ppage) or (ln["page"] == ppage and ln["y"] > py)
                before = True
                if n_ppage is not None and n_py is not None:
                    before = (ln["page"] < n_ppage) or (ln["page"] == n_ppage and ln["y"] < n_py)
                if after and before:
                    window_lines.append(ln)
            child_segments = split_children_in_parent_window(window_lines, child_specs, left_margin=95, min_title_len=5)
            for cnum, content in child_segments.items():
                try:
                    rowcount = update_topic_text(cursor, chapter_id, cnum, content)
                    if rowcount > 0:
                        child_updates += 1
                        updated_topic_numbers.add(cnum)
                        log(f"[P2][SPLIT] child {cnum} <- parent {pnum} (len={len(content)})")
                    else:
                        log(f"[P2][MISS] No row for child {cnum}")
                except Exception as e:
                    log(f"[P2][ERROR] child {cnum}: {e}")
        if child_updates:
            try:
                conn.commit()
            except Exception as e:
                log(f"[P2][ERROR] commit: {e}")
                conn.rollback()
    log(f"[P2] Child updates from span slicing: {child_updates}")

    # Fallback decision
    need_ocr = False
    if len(topic_map) < OCR_MIN_HEADINGS_THRESHOLD:
        log(f"[OCR] Trigger: text-layer extracted only {len(topic_map)} (<{OCR_MIN_HEADINGS_THRESHOLD})")
        need_ocr = True
    elif child_updates < OCR_CHILD_MIN_FOUND:
        log(f"[OCR] Trigger: child slicing found only {child_updates} (<{OCR_CHILD_MIN_FOUND})")
        need_ocr = True

    # Pass 3: OCR fallback
    if need_ocr:
        log("[P3][OCR] Running Tesseract fallback...")
        ocr_children_map = children_map
        ocr_map = ocr_extract_topics(
            pdf_path,
            csv_children_map=ocr_children_map,
            tesseract_bin=TESSERACT_EXE,
            lang=OCR_LANG,
            zoom=OCR_ZOOM,
            fuzzy_threshold=OCR_FUZZY_THRESHOLD
        )
        ocr_updates = 0
        for num, content in ocr_map.items():
            if not content or len(content.strip()) < 20:
                continue
            try:
                rowcount = update_topic_text(cursor, chapter_id, num.strip().strip("."), content)
                if rowcount > 0:
                    ocr_updates += 1
                    updated_topic_numbers.add(num.strip().strip("."))
                    log(f"[P3][OCR] updated {num} (len={len(content)})")
            except Exception as e:
                log(f"[P3][ERROR] Update {num}: {e}")
        if ocr_updates:
            try:
                conn.commit()
            except Exception as e:
                log(f"[P3][ERROR] commit: {e}")
                conn.rollback()
        log(f"[P3] OCR updates written: {ocr_updates}")

    # Final missing list
    try:
        db_set_after = fetch_db_topic_numbers(cursor, chapter_id)
        missing = sorted(db_set_after - updated_topic_numbers, key=lambda s: [int(x) for x in s.split(".") if x.isdigit()])
        if missing:
            preview = ", ".join(missing[:60])
            log(f"[MISSING] {len(missing)} topics still without text: {preview}{' ...' if len(missing)>60 else ''}")
        else:
            log("[MISSING] None — all topics in this chapter have text.")
    except Exception as e:
        log(f"[ERROR] Missing report failed: {e}")

    cursor.close()
    conn.close()
    log("[DONE] Chapter fill complete.")


if __name__ == "__main__":
    main()
