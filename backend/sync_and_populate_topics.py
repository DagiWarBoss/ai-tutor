import os
import re
import csv
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Set

import fitz  # PyMuPDF
import psycopg2
from dotenv import load_dotenv

# =========================
# Configuration
# =========================
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CSV_PATH = "extracted_headings_all_subjects.csv"  # authoritative topic list you uploaded

# DRY_RUN: if True, no DB writes; only logs
DRY_RUN = False

# FALLBACK_TO_PARENT: when a leaf topic_number is missing in DB, write to nearest parent (e.g., 1.3.4 -> 1.3 -> 1)
FALLBACK_TO_PARENT = True

# AUTO_FILL_FROM_PARENT: after a chapter finishes, copy nearest updated parent's full_text
# into DB topics that exist but did not get text in this run (best-effort). Off by default.
AUTO_FILL_FROM_PARENT = False

# Optional: per-chapter remap for edition drifts (use sparingly)
TOPIC_NUMBER_REMAP: Dict[int, Dict[str, str]] = {}

load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# Numbered heading like "4.3.2 Title"
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


# =========================
# CSV (authoritative topics) helpers
# =========================
def load_authoritative_topics(csv_path: str) -> Dict[Tuple[str, str, str], List[Tuple[str, str]]]:
    """
    Return mapping: (subject, class, chapter_file) -> list of (heading_number, heading_text) in CSV order.
    """
    topics_map: Dict[Tuple[str, str, str], List[Tuple[str, str]]] = {}
    if not os.path.exists(csv_path):
        log(f"[ERROR] CSV not found at {csv_path}")
        return topics_map
    with open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row["subject"]
            class_ = row["class"]
            chapter_file = row["chapter_file"]
            heading_number = row["heading_number"]
            heading_text = row["heading_text"]
            key = (subject, class_, chapter_file)
            topics_map.setdefault(key, []).append((heading_number.strip().strip("."), heading_text))
    log(f"[INFO] Loaded authoritative topics from CSV for {len(topics_map)} chapters")
    return topics_map


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
    """
    Returns {topic_number -> id} for all topics in this chapter.
    """
    cursor.execute("SELECT id, topic_number FROM topics WHERE chapter_id = %s", (chapter_id,))
    rows = cursor.fetchall()
    return {row[1]: row[0] for row in rows}


def fetch_db_topic_numbers(cursor, chapter_id: int) -> Set[str]:
    cursor.execute("SELECT topic_number FROM topics WHERE chapter_id = %s", (chapter_id,))
    return {r[0] for r in cursor.fetchall()}


def insert_topic(cursor, chapter_id: int, topic_number: str, title: Optional[str]):
    """
    Insert a topic row if not present. We attempt with name column first; fallback to minimal if schema differs.
    """
    try:
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (chapter_id, topic_number, title)
        )
    except Exception:
        cursor.execute(
            "INSERT INTO topics (chapter_id, topic_number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chapter_id, topic_number)
        )


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


def list_missing_topics(db_topic_numbers: Set[str], updated_topic_numbers: Set[str]) -> List[str]:
    def key_num(s: str):
        return [int(x) for x in s.split(".") if x.isdigit()]
    return sorted(db_topic_numbers - updated_topic_numbers, key=key_num)


# =========================
# PDF parsing helpers
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
    """
    Returns number -> merged text between this anchor and the next numbered anchor.
    Important: We DO NOT drop numeric lines inside sections anymore.
    We only skip a block if it starts with any detected heading number.
    """
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

    log(f"[DEBUG] Total text blocks collected: {len(all_blocks)}")

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

            # Skip only real heading lines (those that start with any known heading number)
            if any(blk["text"].startswith(num) for num in heading_numbers):
                continue

            chunks.append(blk["text"])

        merged = "\n".join(chunks).strip()
        topic_text[a.number] = merged
        log(f"[DEBUG] Topic {a.number} content length: {len(merged)}")

    return topic_text


def extract_topic_texts_from_pdf(pdf_path: str) -> Dict[str, str]:
    """
    Returns mapping topic_number -> content extracted
    """
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
# Main pipeline
# =========================
def main():
    # Load authoritative topics from CSV
    csv_topics = load_authoritative_topics(CSV_PATH)

    # DB connect
    try:
        conn, cursor = connect_db()
    except Exception as e:
        log(f"[ERROR] DB connection failed: {e}")
        return

    # Load chapters and subjects
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

        # 1) Sync: ensure every topic in CSV exists in DB for this chapter
        csv_list = csv_topics.get(csv_key, [])
        csv_numbers = [num for num, _ in csv_list]
        csv_set = set(csv_numbers)

        try:
            db_set = fetch_db_topic_numbers(cursor, chapter_id)
        except Exception as e:
            log(f"[ERROR] Could not fetch DB topics for chapter_id={chapter_id}: {e}")
            continue

        missing_in_db = sorted(csv_set - db_set, key=lambda s: [int(x) for x in s.split('.') if x.isdigit()])
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

        # 2) Extract text from PDF
        topic_map = extract_topic_texts_from_pdf(pdf_path)  # {number -> content}

        # 3) Update DB full_text
        updated = 0
        skipped = 0
        updated_topic_numbers: Set[str] = set()

        for number, content in topic_map.items():
            if not content or len(content.strip()) < 20:
                skipped += 1
                log(f"[WARN] Skipping topic {number}: empty/too short content (len={len(content or '')})")
                continue

            db_number = number.strip().strip(".")
            # Optional remap
            if chapter_id in TOPIC_NUMBER_REMAP and db_number in TOPIC_NUMBER_REMAP[chapter_id]:
                db_number = TOPIC_NUMBER_REMAP[chapter_id][db_number]

            try:
                if DRY_RUN:
                    log(f"[DRY-RUN] Would update chapter_id={chapter_id} topic_number='{db_number}' len={len(content)}")
                    updated += 1
                    updated_topic_numbers.add(db_number)
                    continue

                rowcount = update_topic_text(cursor, chapter_id, db_number, content)
                log(f"[DEBUG] Update chapter_id={chapter_id} topic={db_number} rows={rowcount} len={len(content)}")

                successful_number = None
                if rowcount > 0:
                    successful_number = db_number
                elif rowcount == 0 and FALLBACK_TO_PARENT:
                    parent = ".".join(db_number.split(".")[:-1])
                    while parent:
                        log(f"[FALLBACK] Trying parent '{parent}' for chapter_id={chapter_id}")
                        rowcount = update_topic_text(cursor, chapter_id, parent, content)
                        if rowcount > 0:
                            log(f"[FALLBACK] Updated parent '{parent}' rows={rowcount}")
                            successful_number = parent
                            break
                        parent = ".".join(parent.split(".")[:-1])

                if rowcount == 0 and successful_number is None:
                    log(f"[DIAG] No rows updated for topic_number='{db_number}'. Listing DB topic_numbers for this chapter:")
                    diagnose_topic_numbers(cursor, chapter_id)

                if successful_number is not None:
                    updated_topic_numbers.add(successful_number)

                updated += rowcount

            except Exception as e:
                log(f"[ERROR] Update failed for chapter_id={chapter_id}, topic={db_number}: {e}")

        # 4) Report DB topics that did NOT get text in this run
        try:
            db_map = fetch_db_topics_map(cursor, chapter_id)  # {topic_number: id}
            db_topic_numbers = set(db_map.keys())
            missing_after_update = list_missing_topics(db_topic_numbers, updated_topic_numbers)

            if missing_after_update:
                log(f"[MISSING] DB topics WITHOUT text update this run for chapter_id={chapter_id} ({chapter_name}):")
                preview = ", ".join(missing_after_update[:100])
                log(f"[MISSING] Count={len(missing_after_update)} | {preview}{' ...' if len(missing_after_update) > 100 else ''}")

                # Optional auto-fill from nearest updated parent
                if AUTO_FILL_FROM_PARENT and not DRY_RUN:
                    def nearest_updated_parent(num: str) -> Optional[str]:
                        parts = num.split(".")
                        while len(parts) > 0:
                            cand = ".".join(parts)
                            if cand in updated_topic_numbers:
                                return cand
                            parts = parts[:-1]
                        return None

                    filled = 0
                    for miss in missing_after_update:
                        parent = nearest_updated_parent(miss)
                        if not parent:
                            continue
                        try:
                            cursor.execute(
                                "SELECT full_text FROM topics WHERE chapter_id = %s AND topic_number = %s",
                                (chapter_id, parent)
                            )
                            row = cursor.fetchone()
                            parent_text = row[0] if row else None
                            if not parent_text or len((parent_text or '').strip()) < 20:
                                continue
                            cursor.execute(
                                "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                                (parent_text, chapter_id, miss)
                            )
                            if cursor.rowcount > 0:
                                filled += cursor.rowcount
                                log(f"[AUTO-FILL] Copied parent '{parent}' content to missing '{miss}' (rows={cursor.rowcount})")
                        except Exception as e:
                            log(f"[AUTO-FILL][ERROR] chapter_id={chapter_id} miss='{miss}': {e}")

                    if filled > 0:
                        log(f"[AUTO-FILL] Filled {filled} missing topics from nearest updated parents for chapter_id={chapter_id}")
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
    log("\n[SUCCESS] Sync + Populate pipeline completed.")
    log("Tip: Re-run later if you adjust PDFs or the CSV; this script keeps DB aligned and reports any gaps.")


if __name__ == "__main__":
    main()
