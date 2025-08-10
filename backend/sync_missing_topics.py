import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv

# =========================
# Configuration
# =========================
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
DRY_RUN = False  # False => will INSERT missing topics and COMMIT
USE_TITLE_FROM_PDF = True  # If True and your DB has a nullable 'name' column, we’ll populate it

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# Regex to capture numbered headings like "4.3.2 Title"
HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b[^\w]*(.*)$")

@dataclass
class HeadingAnchor:
    number: str
    title: str
    page: int
    y: float
    x: float
    size: float
    bold: bool

def log(msg: str):
    print(msg, flush=True)

# ------------- DB helpers -------------
def db_connect():
    log("[INFO] Connecting to Supabase/Postgres...")
    conn = psycopg2.connect(SUPABASE_URI)
    conn.autocommit = False
    return conn, conn.cursor()

def fetch_chapters_and_subjects(cursor):
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters ORDER BY id")
    chapters = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sid: sname for sid, sname in cursor.fetchall()}
    log(f"[INFO] Chapters to scan: {len(chapters)}")
    return chapters, subjects

def fetch_topic_numbers_for_chapter(cursor, chapter_id: int) -> List[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s ORDER BY topic_number", (chapter_id,))
    return [r[0] for r in cursor.fetchall()]

def insert_topic(cursor, chapter_id: int, topic_number: str, title: Optional[str]):
    if USE_TITLE_FROM_PDF:
        try:
            cursor.execute(
                "INSERT INTO topics (chapter_id, topic_number, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (chapter_id, topic_number, title)
            )
        except Exception:
            # Fallback: if 'name' column doesn't exist or is NOT NULL elsewhere, try minimal insert
            cursor.execute(
                "INSERT INTO topics (chapter_id, topic_number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (chapter_id, topic_number)
            )
    else:
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chapter_id, topic_number)
        )

# ------------- PDF parsing helpers -------------
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

def normalize_topic_number(text: str) -> Optional[str]:
    m = HEADING_NUMBER_RE.match(text)
    if not m:
        return None
    return m.group(1).strip(". ")

def toc_to_anchors(toc) -> List[HeadingAnchor]:
    anchors = []
    for level, title, page1 in toc:
        if not isinstance(title, str):
            continue
        num = normalize_topic_number(title)
        if not num:
            continue
        page_idx = max(0, page1 - 1)
        anchors.append(HeadingAnchor(number=num, title=(HEADING_NUMBER_RE.match(title).group(2) or "").strip(),
                                     page=page_idx, y=0.0, x=0.0, size=12.0, bold=False))
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
                is_heading = (x0 < 90) and ((size >= body_size + 1.0) or (bold and not body_bold)) and len(title) >= 2
                if is_heading:
                    number = m.group(1).strip(". ")
                    anchors.append(HeadingAnchor(number=number, title=title, page=page_idx, y=float(y0), x=float(x0), size=size, bold=bold))
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

def extract_topic_numbers_from_pdf(pdf_path: str) -> Dict[str, str]:
    """
    Returns mapping: topic_number -> title (best-effort; title may be empty).
    """
    if not os.path.exists(pdf_path):
        log(f"[WARN] PDF not found: {pdf_path}")
        return {}
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log(f"[ERROR] Could not open PDF '{pdf_path}': {e}")
        return {}

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
    doc.close()

    result: Dict[str, str] = {}
    for a in anchors:
        result[a.number] = a.title or None
    return result

# ------------- Main sync pipeline -------------
def main():
    try:
        conn, cursor = db_connect()
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

    total_missing_inserted = 0
    for chapter_id, chapter_name, class_number, subject_id in chapters:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, str(class_number), pdf_filename)

        log(f"\n[INFO] Chapter {chapter_id}: '{chapter_name}' | Class {class_number} | Subject '{subject_name}'")
        log(f"[INFO] PDF path: {pdf_path}")

        extracted = extract_topic_numbers_from_pdf(pdf_path)  # {num: title}
        if not extracted:
            log("[WARN] No topic numbers extracted from PDF; skipping sync for this chapter.")
            continue

        try:
            db_nums = set(fetch_topic_numbers_for_chapter(cursor, chapter_id))
        except Exception as e:
            log(f"[ERROR] Could not fetch DB topics for chapter_id={chapter_id}: {e}")
            continue

        pdf_nums = set(extracted.keys())
        missing = sorted(pdf_nums - db_nums, key=lambda s: [int(x) for x in s.split('.') if x.isdigit()])

        log(f"[DIFF] Extracted={len(pdf_nums)} | In DB={len(db_nums)} | Missing to insert={len(missing)}")
        if missing:
            log(f"[DIFF] Missing list (first 40): {missing[:40]}{' ...' if len(missing) > 40 else ''}")

        inserted_here = 0
        for num in missing:
            title = extracted.get(num)
            try:
                if DRY_RUN:
                    log(f"[DRY-RUN] Would INSERT topic: chapter_id={chapter_id}, topic_number='{num}', name='{title}'")
                    inserted_here += 1
                else:
                    insert_topic(cursor, chapter_id, num, title)
                    inserted_here += 1
            except Exception as e:
                log(f"[ERROR] INSERT failed for chapter_id={chapter_id}, topic_number='{num}': {e}")

        total_missing_inserted += inserted_here
        log(f"[INFO] Chapter sync summary: inserted={inserted_here}, existing={len(db_nums)}, extracted={len(pdf_nums)}")

        if not DRY_RUN:
            try:
                conn.commit()
            except Exception as e:
                log(f"[ERROR] Commit failed for chapter_id={chapter_id}: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    log(f"\n[SUCCESS] Sync completed. Missing topics inserted: {total_missing_inserted}. Now re-run your extractor to populate full_text.")
    log("Next: python populate_topics_from_pdfs.py")

if __name__ == "__main__":
    main()
