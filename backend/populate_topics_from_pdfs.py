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

# If True, only logs what would be done.
DRY_RUN = False

# If True, when a leaf topic_number is missing in DB (rows=0),
# try to update its nearest parent (e.g., 1.3.4 -> 1.3 -> 1).
FALLBACK_TO_PARENT = True

# Optional: If some PDFs/chapters truly use a different numbering
# and you need to bridge temporarily, fill this per-chapter map:
# TOPIC_NUMBER_REMAP = {
#   chapter_id: { "extracted_number": "db_number", ... }
# }
TOPIC_NUMBER_REMAP: Dict[int, Dict[str, str]] = {}

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# Numbered heading like "4.3.2 Title". We only treat these as anchors.
HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b[^\w]*(.*)$")


@dataclass
class HeadingAnchor:
    number: str  # like "4.1", "4.2.3"
    title: str   # rest of the line after number
    page: int
    y: float
    x: float
    size: float
    bold: bool


def log(msg: str):
    print(msg, flush=True)


# =========================
# DB helpers
# =========================
def connect_db():
    log("[INFO] Connecting to Supabase/Postgres...")
    conn = psycopg2.connect(SUPABASE_URI)
    conn.autocommit = False
    return conn, conn.cursor()


def update_topic_text(cursor, chapter_id: int, topic_number: str, content: str) -> int:
    cursor.execute(
        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
        (content, chapter_id, topic_number)
    )
    return cursor.rowcount


def diagnose_topic_numbers(cursor, chapter_id: int) -> List[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s ORDER BY topic_number", (chapter_id,))
    rows = cursor.fetchall()
    nums = [r[0] for r in rows]
    log(f"[DIAG] Existing topic_numbers in DB for chapter_id={chapter_id}: {nums[:50]}{' ...' if len(nums)>50 else ''}")
    return nums


# =========================
# PDF parsing helpers
# =========================
def get_body_font(doc) -> Tuple[float, bool]:
    font_counts = Counter()
    for page_idx, page in enumerate(doc):
        if page_idx > 10:  # first ~11 pages are enough to infer body
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
        title_text = (HEADING_NUMBER_RE.match(title).group(2) or "").strip()
        anchors.append(HeadingAnchor(number=num, title=title_text, page=page_idx,
                                     y=0.0, x=0.0, size=12.0, bold=False))
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
                    anchors.append(
                        HeadingAnchor(number=number, title=title, page=page_idx, y=float(y0), x=float(x0), size=size, bold=bold)
                    )
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
    """
    Returns number -> merged text between this anchor and the next numbered anchor.
    Important change: we DO NOT drop numeric lines inside sections anymore.
    We only skip a block if it starts with any detected anchor number.
    """
    topic_text: Dict[str, str] = {}
    if not anchors:
        return topic_text

    # Collect all text blocks with positions
    all_blocks = []
    for page_idx, page in enumerate(doc):
        # 'blocks' preserves reading order and block positions
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

    log(f"[DEBUG] Total text blocks collected: {len(all_blocks)}")

    # Precompute a set of heading number prefixes for fast check
    heading_numbers = [a.number for a in anchors]

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

            # Skip only real headings: lines that begin with any known heading number (e.g., "1.7", "1.7.2")
            if any(blk["text"].startswith(num) for num in heading_numbers):
                continue

            chunks.append(blk["text"])

        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
        log(f"[DEBUG] Topic {a.number} content length: {len(merged)}")

    return topic_text


def process_single_pdf(doc, pdf_path: str) -> Dict[str, str]:
    """
    Returns mapping topic_number -> content extracted
    """
    log(f"[INFO] Processing PDF: {pdf_path}")
    toc = read_toc(doc)
    anchors: List[HeadingAnchor] = []

    if toc:
        anchors = toc_to_anchors(toc)
        # Require >=2 to give a meaningful range; otherwise, fall back
        if len(anchors) < 2:
            log("[WARN] TOC present but insufficient numbered anchors; using layout fallback.")
            anchors = []

    if not anchors:
        body_size, body_bold = get_body_font(doc)
        anchors = extract_numbered_headings_by_layout(doc, body_size, body_bold)

    anchors = dedupe_and_sort_anchors(anchors)
    if not anchors:
        log("[ERROR] No numbered headings detected; cannot segment topics.")
        return {}

    return collect_text_between_anchors(doc, anchors)


# =========================
# Main pipeline
# =========================
def main():
    # DB connect
    try:
        conn, cursor = connect_db()
    except Exception as e:
        log(f"[ERROR] DB connection failed: {e}")
        return

    # Load chapters and subjects
    try:
        cursor.execute("SELECT id, name, class_number, subject_id FROM chapters ORDER BY id")
        chapters = cursor.fetchall()
        log(f"[INFO] Chapters to process: {len(chapters)}")

        cursor.execute("SELECT id, name FROM subjects")
        subjects = {sid: sname for sid, sname in cursor.fetchall()}
    except Exception as e:
        log(f"[ERROR] Failed loading chapters/subjects: {e}")
        cursor.close()
        conn.close()
        return

    for chapter_id, chapter_name, class_number, subject_id in chapters:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, str(class_number), pdf_filename)

        log(f"\n[INFO] Chapter {chapter_id}: '{chapter_name}' | Class {class_number} | Subject '{subject_name}'")
        log(f"[INFO] PDF path: {pdf_path}")

        if not os.path.exists(pdf_path):
            log(f"[WARN] PDF not found, skipping: {pdf_path}")
            continue

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            log(f"[ERROR] Could not open PDF '{pdf_path}': {e}")
            continue

        topic_map = process_single_pdf(doc, pdf_path)
        doc.close()

        if not topic_map:
            log("[WARN] No topics extracted for this chapter. Running diagnostics for topic_number values in DB.")
            try:
                diagnose_topic_numbers(cursor, chapter_id)
            except Exception as e:
                log(f"[ERROR] Diagnostics failed: {e}")
            continue

        updated = 0
        skipped = 0

        for number, content in topic_map.items():
            # Skip obviously empty captures
            if not content or len(content.strip()) < 20:
                skipped += 1
                log(f"[WARN] Skipping topic {number}: empty/too short content (len={len(content or '')})")
                continue

            # Normalize and apply optional remap
            db_number = number.strip().strip(".")
            if chapter_id in TOPIC_NUMBER_REMAP and db_number in TOPIC_NUMBER_REMAP[chapter_id]:
                db_number = TOPIC_NUMBER_REMAP[chapter_id][db_number]

            try:
                if DRY_RUN:
                    log(f"[DRY-RUN] Would update chapter_id={chapter_id} topic_number='{db_number}' len={len(content)}")
                    updated += 1
                    continue

                rowcount = update_topic_text(cursor, chapter_id, db_number, content)
                log(f"[DEBUG] Update chapter_id={chapter_id} topic={db_number} rows={rowcount} len={len(content)}")

                if rowcount == 0 and FALLBACK_TO_PARENT:
                    # Try closest parent chain: 1.3.4 -> 1.3 -> 1
                    parent = ".".join(db_number.split(".")[:-1])
                    while parent:
                        log(f"[FALLBACK] Trying parent '{parent}' for chapter_id={chapter_id}")
                        rowcount = update_topic_text(cursor, chapter_id, parent, content)
                        if rowcount > 0:
                            log(f"[FALLBACK] Updated parent '{parent}' rows={rowcount}")
                            break
                        parent = ".".join(parent.split(".")[:-1])

                if rowcount == 0:
                    log(f"[DIAG] No rows updated for topic_number='{db_number}'. Listing DB topic_numbers for this chapter:")
                    diagnose_topic_numbers(cursor, chapter_id)

                updated += rowcount

            except Exception as e:
                log(f"[ERROR] Update failed for chapter_id={chapter_id}, topic={db_number}: {e}")

        log(f"[INFO] Chapter summary: updated={updated}, skipped={skipped}, extracted={len(topic_map)}")

        if not DRY_RUN:
            try:
                conn.commit()
            except Exception as e:
                log(f"[ERROR] Commit failed: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    log("\n[SUCCESS] Topic extraction pipeline completed.")


if __name__ == "__main__":
    main()
