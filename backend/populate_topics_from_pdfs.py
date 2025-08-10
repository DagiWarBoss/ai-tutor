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
DRY_RUN = False  # False => will COMMIT updates to Supabase Postgres

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# Optional: targeted remaps for extracted -> DB topic_number, keyed by chapter_id
TOPIC_NUMBER_REMAP: Dict[int, Dict[str, str]] = {
    # Example usage:
    # 1: {"1.3.4": "1.3.4.0"},
}
FALLBACK_TO_PARENT = False  # If True, when a leaf number missing, roll up to nearest parent (e.g., 1.3.4 -> 1.3)

# =========================
# Utilities
# =========================
HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b[^\w]*(.*)$")

@dataclass
class HeadingAnchor:
    number: str  # like "4.1", "4.2.3"
    title: str   # rest of line
    page: int
    y: float
    x: float
    size: float
    bold: bool

def debug(msg: str):
    print(msg, flush=True)

def connect_db():
    debug("[INFO] Connecting to Supabase/Postgres...")
    conn = psycopg2.connect(SUPABASE_URI)
    conn.autocommit = False
    return conn, conn.cursor()

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
        debug("[DEBUG] No font spans found; fallback body font size=10, bold=False")
        return 10.0, False
    (size, is_bold), _ = font_counts.most_common(1)[0]
    debug(f"[DEBUG] Body font detected: size={size}, bold={is_bold}")
    return float(size), bool(is_bold)

def read_toc(doc) -> List[Tuple[int, str, int]]:
    try:
        toc = doc.get_toc(simple=True) or []
        debug(f"[INFO] TOC entries found: {len(toc)}")
        return toc
    except Exception as e:
        debug(f"[WARN] get_toc failed: {e}")
        return []

def normalize_topic_number(text: str) -> Optional[str]:
    m = HEADING_NUMBER_RE.match(text)
    if not m:
        return None
    return m.group(1).strip(". ")

def toc_to_anchors(doc, toc: List[List]) -> List[HeadingAnchor]:
    anchors = []
    for level, title, page1 in toc:
        if not isinstance(title, str):
            continue
        num = normalize_topic_number(title)
        if not num:
            continue
        page_idx = max(0, page1 - 1)
        anchors.append(HeadingAnchor(number=num, title=title, page=page_idx, y=0.0, x=0.0, size=12.0, bold=False))
    debug(f"[INFO] TOC-derived anchors: {len(anchors)}")
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

                is_heading = (x0 < 90) and ((size >= body_size + 1.0) or (bold and not body_bold))
                # Enforce non-empty title to avoid spurious anchors like "1.1 "
                title = (m.group(2) or "").strip()
                if is_heading and len(title) >= 2:
                    number = m.group(1).strip(". ")
                    anchors.append(HeadingAnchor(number=number, title=title, page=page_idx, y=float(y0), x=float(x0), size=size, bold=bold))
                    debug(f"[DEBUG] Heading p{page_idx+1} y={y0:.1f} x={x0:.1f} size={size:.1f} bold={bold}: '{number} {title}'")
    debug(f"[INFO] Layout-derived anchors: {len(anchors)}")
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
    debug(f"[INFO] Unique anchors after de-dup: {len(uniq)}")
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

    debug(f"[DEBUG] Total text blocks collected: {len(all_blocks)}")

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
            if after_start and before_end:
                if HEADING_NUMBER_RE.match(blk["text"]):
                    continue
                chunks.append(blk["text"])
        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
        debug(f"[DEBUG] Topic {a.number} content length: {len(merged)}")

    return topic_text

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
    debug(f"[DIAG] Existing topic_numbers in DB for chapter_id={chapter_id}: {nums[:50]}{' ...' if len(nums)>50 else ''}")
    return nums

def diff_numbers(extracted_nums: List[str], db_nums: List[str]):
    ex = set(extracted_nums)
    db = set(db_nums)
    miss = sorted(ex - db)
    extra = sorted(db - ex)
    debug(f"[DIFF] Missing in DB: {miss[:50]}{' ...' if len(miss)>50 else ''}")
    debug(f"[DIFF] Extra in DB: {extra[:50]}{' ...' if len(extra)>50 else ''}")

def process_single_pdf(doc, pdf_path: str) -> Dict[str, str]:
    debug(f"[INFO] Processing PDF: {pdf_path}")
    toc = read_toc(doc)
    if toc:
        anchors = toc_to_anchors(doc, toc)
        if len(anchors) >= 2:
            anchors = dedupe_and_sort_anchors(anchors)
            if anchors:
                return collect_text_between_anchors(doc, anchors)
        else:
            debug("[WARN] TOC present but insufficient numbered anchors; trying layout fallback.")

    body_size, body_bold = get_body_font(doc)
    anchors = extract_numbered_headings_by_layout(doc, body_size, body_bold)
    anchors = dedupe_and_sort_anchors(anchors)
    if not anchors:
        debug("[ERROR] No headings detected via fallback; cannot segment topics.")
        return {}
    return collect_text_between_anchors(doc, anchors)

def main():
    # DB connect
    try:
        conn, cursor = connect_db()
    except Exception as e:
        debug(f"[ERROR] DB connection failed: {e}")
        return

    # Load chapters and subjects
    try:
        cursor.execute("SELECT id, name, class_number, subject_id FROM chapters ORDER BY id")
        chapters = cursor.fetchall()
        debug(f"[INFO] Chapters to process: {len(chapters)}")

        cursor.execute("SELECT id, name FROM subjects")
        subjects = {sid: sname for sid, sname in cursor.fetchall()}
    except Exception as e:
        debug(f"[ERROR] Failed loading chapters/subjects: {e}")
        cursor.close()
        conn.close()
        return

    for chapter_id, chapter_name, class_number, subject_id in chapters:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, str(class_number), pdf_filename)

        debug(f"\n[INFO] Chapter {chapter_id}: '{chapter_name}' | Class {class_number} | Subject '{subject_name}'")
        debug(f"[INFO] PDF path: {pdf_path}")

        if not os.path.exists(pdf_path):
            debug(f"[WARN] PDF not found, skipping: {pdf_path}")
            continue

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            debug(f"[ERROR] Could not open PDF '{pdf_path}': {e}")
            continue

        topic_map = process_single_pdf(doc, pdf_path)
        doc.close()

        if not topic_map:
            debug("[WARN] No topics extracted for this chapter. Running diagnostics for topic_number values in DB.")
            try:
                diagnose_topic_numbers(cursor, chapter_id)
            except Exception as e:
                debug(f"[ERROR] Diagnostics failed: {e}")
            continue

        # Compute diffs vs DB to help spot mismatches early
        try:
            db_nums = diagnose_topic_numbers(cursor, chapter_id)
            extracted_nums = list(topic_map.keys())
            diff_numbers(extracted_nums, db_nums)
        except Exception as e:
            debug(f"[ERROR] Diff computation failed: {e}")

        updated = 0
        skipped = 0

        for number, content in topic_map.items():
            if not content or len(content.strip()) < 20:
                skipped += 1
                debug(f"[WARN] Skipping topic {number}: empty/too short content (len={len(content or '')})")
                continue

            # Apply optional chapter-specific remaps
            db_number = TOPIC_NUMBER_REMAP.get(chapter_id, {}).get(number, number)

            try:
                if DRY_RUN:
                    debug(f"[DRY-RUN] Would update chapter_id={chapter_id} topic_number='{db_number}' len={len(content)}")
                    updated += 1
                else:
                    rowcount = update_topic_text(cursor, chapter_id, db_number, content)
                    debug(f"[DEBUG] Update chapter_id={chapter_id} topic={db_number} rows={rowcount} len={len(content)}")

                    if rowcount == 0 and FALLBACK_TO_PARENT:
                        parent = ".".join(db_number.split(".")[:-1])
                        while parent:
                            debug(f"[FALLBACK] Trying parent '{parent}' for chapter_id={chapter_id}")
                            rowcount = update_topic_text(cursor, chapter_id, parent, content)
                            if rowcount > 0:
                                debug(f"[FALLBACK] Updated parent '{parent}' rows={rowcount}")
                                break
                            parent = ".".join(parent.split(".")[:-1])

                    if rowcount == 0:
                        debug(f"[DIAG] No rows updated for topic_number='{db_number}'. Listing DB topic_numbers for this chapter:")
                        diagnose_topic_numbers(cursor, chapter_id)

                    updated += rowcount
            except Exception as e:
                debug(f"[ERROR] Update failed for chapter_id={chapter_id}, topic={db_number}: {e}")

        debug(f"[INFO] Chapter summary: updated={updated}, skipped={skipped}, extracted={len(topic_map)}")

        if not DRY_RUN:
            try:
                conn.commit()
            except Exception as e:
                debug(f"[ERROR] Commit failed: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    debug("\n[SUCCESS] Topic extraction pipeline completed.")

if __name__ == "__main__":
    main()
