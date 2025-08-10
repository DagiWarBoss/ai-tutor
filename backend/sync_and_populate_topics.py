import os
import re
import csv
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Set

# Third-party
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

# =========================
# Configuration
# =========================
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"

# Safety: no risky content moves
DRY_RUN = False
FALLBACK_TO_PARENT = False
AUTO_FILL_FROM_PARENT = False

# OCR fallback settings
OCR_MIN_HEADINGS_THRESHOLD = 3     # if text-layer finds less than this, trigger OCR
OCR_ZOOM = 4.0                     # 72dpi * 4 => ~288dpi
OCR_LANG = "eng"
OCR_FUZZY_THRESHOLD = 85           # child title matching threshold

# Tesseract path (None if in PATH; set full path on Windows if needed)
TESSERACT_EXE = None  # e.g., r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Regex
HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b[^\w]*(.*)$")
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


# =========================
# CSV helpers
# =========================
def load_authoritative_topics(csv_path: str) -> Dict[Tuple[str, str, str], List[Tuple[str, str]]]:
    topics_map: Dict[Tuple[str, str, str], List[Tuple[str, str]]] = {}
    if not os.path.exists(csv_path):
        log(f"[ERROR] CSV not found at {csv_path}")
        return topics_map
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row["subject"]
            class_ = row["class"]
            chapter_file = row["chapter_file"]
            heading_number = (row["heading_number"] or "").strip().strip(".")
            heading_text = row.get("heading_text", None)
            key = (subject, class_, chapter_file)
            topics_map.setdefault(key, []).append((heading_number, heading_text))
    log(f"[INFO] Loaded authoritative topics from CSV for {len(topics_map)} chapters")
    return topics_map


def build_csv_children_map(csv_list: List[Tuple[str, Optional[str]]]) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    by_parent: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    for n, t in csv_list:
        if not n:
            continue
        parent = ".".join(n.split(".")[:-1])
        if parent:
            by_parent.setdefault(parent, []).append((n, t))
    return by_parent


# =========================
# DB helpers
# =========================
def connect_db():
    log("[INFO] Connecting to Supabase/Postgres...")
    conn = psycopg2.connect(SUPABASE_URI)
    conn.autocommit = False
    return conn, conn.cursor()


def fetch_chapters_and_subjects(cursor):
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters ORDER BY id")
    chapters = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sid: sname for sid, sname in cursor.fetchall()}
    log(f"[INFO] Chapters to process: {len(chapters)}")
    return chapters, subjects


def fetch_db_topics_map(cursor, chapter_id: int) -> Dict[str, int]:
    cursor.execute("SELECT id, topic_number FROM topics WHERE chapter_id = %s", (chapter_id,))
    rows = cursor.fetchall()
    return {row[1]: row[0] for row in rows}


def fetch_db_topic_numbers(cursor, chapter_id: int) -> Set[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s", (chapter_id,))
    return {r[0] for r in cursor.fetchall()}


def insert_topic(cursor, chapter_id: int, topic_number: str, title: Optional[str]):
    try:
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (chapter_id, topic_number, title),
        )
    except Exception:
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chapter_id, topic_number),
        )


def update_topic_text(cursor, chapter_id: int, topic_number: str, content: str) -> int:
    cursor.execute(
        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
        (content, chapter_id, topic_number),
    )
    return cursor.rowcount


def diagnose_topic_numbers(cursor, chapter_id: int) -> List[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s ORDER BY topic_number", (chapter_id,))
    rows = cursor.fetchall)
    # Fix: fetchall() needs to be called
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s ORDER BY topic_number", (chapter_id,))
    rows = cursor.fetchall()
    nums = [r[0] for r in rows]
    log(f"[DIAG] Existing topic_numbers in DB for chapter_id={chapter_id}: {nums[:50]}{' ...' if len(nums)>50 else ''}")
    return nums


def list_missing_topics(db_topic_numbers: Set[str], updated_topic_numbers: Set[str]) -> List[str]:
    def key_num(s: str):
        return [int(x) for x in s.split(".") if x.isdigit()]
    return sorted(db_topic_numbers - updated_topic_numbers, key=key_num)


# =========================
# Text-layer extractor
# =========================
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
        log("[DEBUG] No font spans found; fallback body font size=10, bold=False")
        return 10.0, False
    (size, bold), _ = font_counts.most_common(1)[0]
    log(f"[DEBUG] Body font detected: size={size}, bold={bold}")
    return float(size), bool(bold)


def read_toc(doc):
    try:
        toc = doc.get_toc(simple=True) or []
        log(f"[INFO] TOC entries found: {len(toc)}")
        return toc
    except Exception as e:
        log(f"[WARN] get_toc failed: {e}")
        return []


def normalize_topic_number_from_text(text: str) -> Optional[str]:
    m = HEADING_NUMBER_RE.match(text)
    if not m:
        return None
    return m.group(1).strip(". ")


def toc_to_anchors(toc) -> List[HeadingAnchor]:
    anchors = []
    for level, title, page1 in toc:
        if not isinstance(title, str):
            continue
        num = normalize_topic_number_from_text(title)
        if not num:
            continue
        page_idx = max(0, page1 - 1)
        m = HEADING_NUMBER_RE.match(title)
        title_text = (m.group(2) or "").strip() if m else ""
        anchors.append(HeadingAnchor(number=num, title=title_text, page=page_idx, y=0.0, x=0.0, size=12.0, bold=False))
    log(f"[INFO] TOC-derived anchors: {len(anchors)}")
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
                    log(f"[DEBUG] Heading candidate p{page_idx+1} y={y0:.1f} x={x0:.1f} size={size:.1f} bold={bold}: '{number} {title}'")
    log(f"[INFO] Layout-derived anchors: {len(anchors)}")
    return anchors


def dedupe_and_sort_anchors(anchors: List[HeadingAnchor]) -> List[HeadingAnchor]:
    seen = set()
    uniq = []
    for a in anchors:
        key = (a.number, a.page, round(a.y, 1))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    uniq.sort(key=lambda h: (h.page, h.y))
    log(f"[INFO] Unique anchors after de-dup: {len(uniq)}")
    return uniq


def collect_text_between_anchors(doc, anchors: List[HeadingAnchor]) -> Dict[str, str]:
    topic_text: Dict[str, str] = {}
    if not anchors:
        return topic_text

    all_blocks = []
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
            all_blocks.append({"page": page_idx, "x": x0, "y": y0, "text": text})

    heading_numbers = [a.number for a in anchors]

    def is_true_heading_line(text: str) -> bool:
        return any(text.startswith(num) for num in heading_numbers)

    for i, a in enumerate(anchors):
        start_page, start_y = a.page, a.y
        if i + 1 < len(anchors):
            b = anchors[i + 1]
            end_page, end_y = b.page, b.y
        else:
            end_page, end_y = float("inf"), float("inf")

        chunks = []
        for blk in all_blocks:
            after_start = blk["page"] > start_page or (blk["page"] == start_page and blk["y"] > start_y)
            before_end = blk["page"] < end_page or (blk["page"] == end_page and blk["y"] < end_y)
            if not (after_start and before_end):
                continue
            if is_true_heading_line(blk["text"]):
                continue
            chunks.append(blk["text"])

        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
        log(f"[DEBUG] Topic {a.number} content length: {len(merged)}")

    return topic_text


def extract_topic_texts_from_pdf(pdf_path: str) -> Dict[str, str]:
    if not os.path.exists(pdf_path):
        log(f"[WARN] PDF not found, skipping: {pdf_path}")
        return {}
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log(f"[ERROR] Could not open PDF '{pdf_path}': {e}")
        return {}

    log(f"[INFO] Processing PDF: {pdf_path}")
    toc = read_toc(doc)
    anchors: List[HeadingAnchor] = []
    if toc:
        anchors = toc_to_anchors(toc)
        if len(anchors) < 2:
            log("[WARN] TOC present but insufficient numbered anchors; using layout fallback.")
            anchors = []

    if not anchors:
        body_size, body_bold = get_body_font(doc)
        anchors = extract_numbered_headings_by_layout(doc, body_size, body_bold)

    anchors = dedupe_and_sort_anchors(anchors)
    if not anchors:
        log("[ERROR] No numbered headings detected; cannot segment topics.")
        doc.close()
        return {}

    topic_text = collect_text_between_anchors(doc, anchors)
    doc.close()
    return topic_text


# =========================
# OCR fallback (built-in)
# =========================
def _norm_spaces(s: str) -> str:
    return SPACE_RE.sub(" ", (s or "").strip())


def _norm_text(s: str) -> str:
    s = _norm_spaces(s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("·", ".")
    return s.lower()


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
        text = _norm_spaces(" ".join(words))
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
        key = (a["number"], a["page"], int(a["y"] / 2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def ocr_best_child_matches_in_window(window_lines: List[Dict],
                                     csv_children: List[Tuple[str, Optional[str]]],
                                     left_margin_px: int = 300,
                                     fuzzy_threshold: int = 85) -> List[Dict]:
    cands = [ln for ln in window_lines if ln["x"] <= left_margin_px]
    results = []
    for child_num, child_title in csv_children:
        if not child_num or not child_title:
            continue
        target = _norm_text(child_title)
        best, best_score = None, -1
        for ln in cands:
            cand_text_norm = _norm_text(ln["text"])
            if HAVE_FUZZ:
                score = fuzz.partial_ratio(target, cand_text_norm)
            else:
                score = 100 if target in cand_text_norm else (90 if cand_text_norm.startswith(target[: max(5, len(target)//2)]) else 0)
            if score > best_score:
                best_score = score
                best = ln
        if best and best_score >= fuzzy_threshold:
            results.append({"type": "csv_child", "number": child_num.strip("."), "page": best["page"], "y": best["y"], "text": best["text"], "score": best_score})
    results.sort(key=lambda a: (a["page"], a["y"]))
    uniq, seen = [], set()
    for a in results:
        key = (a["number"], a["page"], int(a["y"] / 2))
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
            merged = _norm_spaces("\n".join(chunks))
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
        merged = _norm_spaces("\n".join(chunks))
        if merged:
            segments[start_anchor["number"]] = merged
    return segments


def ocr_extract_topics(pdf_path: str,
                       csv_children_map: Optional[Dict[str, List[Tuple[str, Optional[str]]]]] = None,
                       tesseract_bin: Optional[str] = None,
                       lang: str = "eng",
                       zoom: float = 4.0,
                       fuzzy_threshold: int = 85) -> Dict[str, str]:
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
            child_anchors = ocr_best_child_matches_in_window(
                window_lines,
                csv_children=child_specs,
                left_margin_px=300,
                fuzzy_threshold=fuzzy_threshold
            )

        segs = ocr_segment_window(lines_sorted, parent, end_parent, child_anchors)
        segments.update(segs)

    return segments


# =========================
# Main
# =========================
def main():
    if TESSERACT_EXE:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

    # CSV
    csv_topics = load_authoritative_topics(CSV_PATH)

    # DB
    try:
        conn, cursor = connect_db()
    except Exception as e:
        log(f"[ERROR] DB connection failed: {e}")
        return

    try:
        chapters, subjects = fetch_chapters_and_subjects(cursor)
    except Exception as e:
        log(f"[ERROR] Failed loading chapters/subjects: {e}")
        cursor.close()
        conn.close()
        return

    for chapter_id, chapter_name, class_number, subject_id in chapters:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        csv_key = (subject_name, str(class_number), pdf_filename)
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, str(class_number), pdf_filename)

        log(f"\n[INFO] Chapter {chapter_id}: '{chapter_name}' | Class {class_number} | Subject '{subject_name}'")
        log(f"[INFO] PDF path: {pdf_path}")

        # Ensure topics exist per CSV
        csv_list = csv_topics.get(csv_key, [])
        csv_numbers = [num for num, _ in csv_list if num]
        csv_set = set(csv_numbers)

        try:
            db_set = fetch_db_topic_numbers(cursor, chapter_id)
        except Exception as e:
            log(f"[ERROR] Could not fetch DB topics for chapter_id={chapter_id}: {e}")
            continue

        missing_in_db = sorted(
            csv_set - db_set, key=lambda s: [int(x) for x in s.split(".") if x.isdigit()]
        )
        log(f"[SYNC] CSV topics={len(csv_set)} | In DB={len(db_set)} | Missing to insert={len(missing_in_db)}")

        if missing_in_db and not DRY_RUN:
            inserted = 0
            csv_title_map = {n: t for n, t in csv_list}
            for num in missing_in_db:
                title = csv_title_map.get(num)
                try:
                    insert_topic(cursor, chapter_id, num, title)
                    inserted += 1
                except Exception as e:
                    log(f"[ERROR] INSERT failed for chapter_id={chapter_id}, topic_number='{num}': {e}")
            if inserted:
                try:
                    conn.commit()
                except Exception as e:
                    log(f"[ERROR] Commit after insert failed: {e}")
                    conn.rollback()
            log(f"[SYNC] Inserted {inserted} missing topics for chapter_id={chapter_id}")

        # Extract via text-layer
        topic_map = extract_topic_texts_from_pdf(pdf_path)

        # OCR fallback if too few headings were extracted
        if not topic_map or len(topic_map) < OCR_MIN_HEADINGS_THRESHOLD:
            log(f"[FALLBACK][OCR] Triggered for chapter_id={chapter_id} (text-layer extracted={len(topic_map) if topic_map else 0})")
            csv_children_map = build_csv_children_map(csv_list)
            ocr_map = ocr_extract_topics(
                pdf_path,
                csv_children_map=csv_children_map,
                tesseract_bin=TESSERACT_EXE,
                lang=OCR_LANG,
                zoom=OCR_ZOOM,
                fuzzy_threshold=OCR_FUZZY_THRESHOLD
            )
            # Use OCR results only if they add value
            if ocr_map:
                topic_map = ocr_map

        # Update DB
        updated = 0
        skipped = 0
        updated_topic_numbers: Set[str] = set()

        for number, content in topic_map.items():
            if not content or len(content.strip()) < 20:
                skipped += 1
                log(f"[WARN] Skipping topic {number}: empty/too short content (len={len(content or '')})")
                continue

            db_number = number.strip().strip(".")
            try:
                if DRY_RUN:
                    log(f"[DRY-RUN] Would update chapter_id={chapter_id} topic_number='{db_number}' len={len(content)}")
                    updated += 1
                    updated_topic_numbers.add(db_number)
                    continue

                rowcount = update_topic_text(cursor, chapter_id, db_number, content)
                log(f"[DEBUG] Update chapter_id={chapter_id} topic={db_number} rows={rowcount} len={len(content)}")

                if rowcount > 0:
                    updated_topic_numbers.add(db_number)
                elif rowcount == 0 and FALLBACK_TO_PARENT:
                    pass  # disabled
                else:
                    log(f"[DIAG] No rows updated for topic_number='{db_number}'. Listing DB topic_numbers for this chapter:")
                    diagnose_topic_numbers(cursor, chapter_id)

                updated += rowcount

            except Exception as e:
                log(f"[ERROR] Update failed for chapter_id={chapter_id}, topic={db_number}: {e}")

        # Missing report
        try:
            db_map = fetch_db_topics_map(cursor, chapter_id)
            db_topic_numbers = set(db_map.keys())
            missing_after_update = list_missing_topics(db_topic_numbers, updated_topic_numbers)
            if missing_after_update:
                log(f"[MISSING] DB topics WITHOUT text update this run for chapter_id={chapter_id} ({chapter_name}):")
                preview = ", ".join(missing_after_update[:100])
                log(f"[MISSING] Count={len(missing_after_update)} | {preview}{' ...' if len(missing_after_update) > 100 else ''}")
            else:
                log(f"[MISSING] None — all DB topics for this chapter were updated this run (or already had content).")
        except Exception as e:
            log(f"[ERROR] Missing-topic report failed for chapter_id={chapter_id}: {e}")

        log(f"[INFO] Chapter summary: updated={updated}, skipped={skipped}, extracted={len(topic_map)}")

        if not DRY_RUN:
            try:
                conn.commit()
            except Exception as e:
                log(f"[ERROR] Commit failed: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    log("\n[SUCCESS] Sync + Populate pipeline completed (no fallback-to-parent, no auto-fill).")


if __name__ == "__main__":
    main()
