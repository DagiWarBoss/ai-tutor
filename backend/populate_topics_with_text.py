import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv
import psycopg2
from collections import Counter
import signal
import time
import traceback

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
PAGE_PROCESS_TIMEOUT = 5  # Seconds to wait before skipping a complex page

# --- Timeout handling ---
class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()

# signal.SIGALRM not supported on Windows PowerShell sometimes; guard it.
try:
    signal.signal(signal.SIGALRM, timeout_handler)
    _HAS_SIGALRM = True
except Exception:
    _HAS_SIGALRM = False

CHAPTER_NUMBER_FALLBACK_MAP = {
    "Some Basic Concepts Of Chemistry.pdf": "1", "Structure Of Atom.pdf": "2",
    "Classification Of Elements And Periodicity.pdf": "3", "Chemical Bonding And Molecular Structure.pdf": "4",
    "Thermodynamics.pdf": "5", "Equilibrium.pdf": "6", "Redox Reactions.pdf": "7",
    "Organic Chemistry Basics.pdf": "8", "Hydrocarbons.pdf": "9",
    "Solutions.pdf": "1", "Electrochemistry.pdf": "2", "Chemical Kinetics.pdf": "3",
    "D And F Block.pdf": "4", "Coordination Compounds.pdf": "5", "Haloalkanes And Haloarenes.pdf": "6",
    "Alcohol Phenols Ethers.pdf": "7", "Aldehydes, Ketones And Carboxylic Acid.pdf": "8",
    "Amines.pdf": "9", "Biomolecules.pdf": "10",
    "Units And Measurements.pdf": "1", "Motion In A Straight Line.pdf": "2", "Motion In A Plane.pdf": "3",
    "Laws Of Motion.pdf": "4", "Work Energy Power.pdf": "5", "System Of Particles And Rotational Motion.pdf": "6",
    "Gravitation.pdf": "7", "Mechanical Properties Of Solids.pdf": "8", "Mechanical Properties Of Fluids.pdf": "9",
    "Thermal Properties Of Matter.pdf": "10", "Thermodynamics.pdf": "11", "Kinetic Theory.pdf": "12",
    "Oscillations.pdf": "13", "Waves.pdf": "14",
    "Electric Charges And Fields.pdf": "1", "Electrostatic Potential And Capacitance.pdf": "2",
    "Current Electricity.pdf": "3", "Moving Charges And Magnetism.pdf": "4", "Magnetism And Matter.pdf": "5",
    "Electromagnetic Induction.pdf": "6", "Alternating Current.pdf": "7", "Electromagnetic Waves.pdf": "8",
    "Ray Optics.pdf": "9", "Wave Optics.pdf": "10", "Dual Nature Of Radiation And Matter.pdf": "11",
    "Atoms.pdf": "12", "Nuclei.pdf": "13", "SemiConductor Electronics.pdf": "14",
}

def dbg(msg: str):
    print(msg, flush=True)

def alarm_start(seconds: int):
    if _HAS_SIGALRM:
        signal.alarm(seconds)

def alarm_clear():
    if _HAS_SIGALRM:
        signal.alarm(0)

def get_most_common_font_info(doc):
    dbg("[DEBUG] Enter get_most_common_font_info")
    t0 = time.time()
    font_counts = Counter()
    for page_num, page in enumerate(doc):
        if page_num > 5:
            dbg("[DEBUG] Font scan: limiting to first 6 pages")
            break
        try:
            alarm_start(PAGE_PROCESS_TIMEOUT)
            blocks = page.get_text("dict")["blocks"]
            alarm_clear()
            for b in blocks:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l.get("spans", []):
                            size = s.get("size", 10)
                            font = s.get("font", "")
                            key = (round(size), "bold" in font.lower())
                            font_counts[key] += 1
        except TimeoutException:
            alarm_clear()
            dbg(f"[WARN] get_most_common_font_info: page {page_num+1} timed out")
            continue
        except Exception as e:
            alarm_clear()
            dbg(f"[ERROR] get_most_common_font_info page {page_num+1}: {e}")
            dbg(traceback.format_exc())
    if not font_counts:
        dbg("[DEBUG] No font spans found; defaulting to size=10, bold=False")
        return (10.0, False)
    (sz, is_bold), count = font_counts.most_common(1)[0]
    dbg(f"[DEBUG] Body font resolved: size={sz}, bold={is_bold} (count={count}) in {time.time()-t0:.2f}s")
    return float(sz), bool(is_bold)

def extract_text_and_headings_with_location(doc, chapter_number):
    dbg(f"[DEBUG] Enter extract_text_and_headings_with_location(chapter_number={chapter_number})")
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    dbg(f"[DEBUG] Body style identified: size ~{body_font_size}, bold: {body_is_bold}")

    # Regex: chapter_number, optional dot-digits up to 5 levels, followed by punctuation/space, then a letter-starting title
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+([A-Za-z].*)$")

    headings, all_text_blocks = [], []
    total_pages = len(doc)
    dbg(f"[DEBUG] Document pages: {total_pages}")

    for page_num, page in enumerate(doc):
        try:
            alarm_start(PAGE_PROCESS_TIMEOUT)
            page_height = page.rect.height
            top_margin, bottom_margin = page_height * 0.10, page_height * 0.90

            # Ordered text blocks for content collection
            blocks = page.get_text("blocks", sort=True)

            # Styled blocks for heading decisions
            styled_blocks = page.get_text("dict", flags=fitz.TEXT_INHIBIT_SPACES)["blocks"]
            alarm_clear()

            dbg(f"[DEBUG] Page {page_num+1}/{total_pages}: blocks={len(blocks)} styled_blocks={len(styled_blocks)}")

            # Collect content blocks (filter out header/footer via margins)
            kept_blocks = 0
            for b in blocks:
                try:
                    x0, y0, x1, y1, block_text_raw, *_rest = b
                    block_text = (block_text_raw or "").strip().replace('\n', ' ')
                    if not block_text:
                        continue
                    if (y0 < top_margin) or (y1 > bottom_margin):
                        # likely header/footer
                        continue
                    all_text_blocks.append({'text': block_text, 'page': page_num, 'y': y0})
                    kept_blocks += 1
                except Exception as e:
                    dbg(f"[WARN] Block parse error on page {page_num+1}: {e}")
                    continue
            dbg(f"[DEBUG] Page {page_num+1}: kept content blocks={kept_blocks}")

            # Detect headings (numbered) using regex + style cue
            accepted_here = 0
            tested_lines = 0
            for b in styled_blocks:
                if "lines" not in b:
                    continue
                for l in b["lines"]:
                    spans = l.get("spans", [])
                    if not spans:
                        continue
                    line_text = "".join(s.get("text", "") for s in spans).strip()
                    if not line_text:
                        continue
                    tested_lines += 1
                    m = pat.match(line_text)
                    if m:
                        first_span = spans[0]
                        span_size = round(first_span.get("size", 10))
                        span_font = first_span.get("font", "")
                        span_is_bold = "bold" in span_font.lower()
                        is_heading_style = (span_size > body_font_size) or (span_is_bold and not body_is_bold)
                        dbg(f"    [DEBUG] Regex matched on p{page_num+1}: '{line_text}'")
                        dbg(f"           Span font='{span_font}', size={span_size}, bold={span_is_bold}, style_ok={is_heading_style}")
                        if is_heading_style:
                            y_pos = b.get('bbox', [0, 0, 0, 0])[1]
                            headings.append({'text': line_text, 'page': page_num, 'y': y_pos})
                            accepted_here += 1
                        else:
                            dbg("           -> Rejected: style not strong enough for heading")
            dbg(f"[DEBUG] Page {page_num+1}: tested_lines={tested_lines}, accepted_headings={accepted_here}")

        except TimeoutException:
            alarm_clear()
            dbg(f"[WARNING] Page {page_num+1} timed out. Skipping its content and headings.")
            continue
        except Exception as e:
            alarm_clear()
            dbg(f"[ERROR] Exception on page {page_num+1}: {e}")
            dbg(traceback.format_exc())
            continue

    # Deduplicate by exact text (keeps last occurrence)
    unique_headings_map = {}
    for h in headings:
        unique_headings_map[h['text']] = h
    unique_headings = list(unique_headings_map.values())

    dbg(f"[DEBUG] Total headings captured (raw)={len(headings)}, unique={len(unique_headings)}")
    dbg(f"[DEBUG] Total content blocks captured={len(all_text_blocks)}")
    return unique_headings, all_text_blocks

def map_text_to_headings(headings, all_text_blocks):
    dbg("[DEBUG] Enter map_text_to_headings")
    topic_content = {}
    sorted_headings = sorted(headings, key=lambda h: (h['page'], h['y']))
    dbg(f"[DEBUG] Sorted headings count={len(sorted_headings)}")

    # Quick index to speed up is_a_heading check
    heading_texts = set(h['text'] for h in sorted_headings)

    for i, heading in enumerate(sorted_headings):
        start_page, start_y = heading['page'], heading['y']
        if i + 1 < len(sorted_headings):
            end_page, end_y = sorted_headings[i+1]['page'], sorted_headings[i+1]['y']
        else:
            end_page, end_y = float('inf'), float('inf')

        dbg(f"[DEBUG] Window for heading[{i}]='{heading['text']}' -> start(p={start_page+1}, y={start_y:.1f}) end(p={end_page if end_page!=float('inf') else 'inf'}, y={end_y if end_y!=float('inf') else 'inf'})")

        content = []
        added_blocks = 0
        skipped_as_heading = 0
        for block in all_text_blocks:
            is_after_start = (block['page'] > start_page) or (block['page'] == start_page and block['y'] > start_y)
            is_before_end = (block['page'] < end_page) or (block['page'] == end_page and block['y'] < end_y)
            if is_after_start and is_before_end:
                # Exclude blocks that equal any heading's exact text (rare but defensive)
                if block['text'] in heading_texts:
                    skipped_as_heading += 1
                    continue
                content.append(block['text'])
                added_blocks += 1

        dbg(f"[DEBUG]   -> collected blocks={added_blocks}, skipped_as_heading={skipped_as_heading}")
        topic_content[heading['text']] = "\n".join(content)

    dbg(f"[DEBUG] map_text_to_headings produced {len(topic_content)} topic entries")
    return topic_content

def main():
    dbg("[BOOT] Starting NCERT extractor with debug logging")
    dbg(f"[BOOT] Using PDF_ROOT_FOLDER='{PDF_ROOT_FOLDER}'")
    dbg(f"[BOOT] SUPABASE_CONNECTION_STRING present={bool(SUPABASE_URI)}")

    # DB connect
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        dbg("[INFO] Connected to Supabase/Postgres")
    except Exception as e:
        dbg(f"[ERROR] Could not connect to Supabase: {e}")
        dbg(traceback.format_exc())
        return

    # Load chapters/subjects
    try:
        cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
        chapters_to_process = cursor.fetchall()
        cursor.execute("SELECT id, name FROM subjects")
        subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}
        dbg(f"[DEBUG] Found {len(chapters_to_process)} chapters")
    except Exception as e:
        dbg(f"[ERROR] Failed to load chapters/subjects: {e}")
        dbg(traceback.format_exc())
        cursor.close()
        conn.close()
        return

    total_updates = 0
    total_topics_mapped = 0

    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        try:
            subject_name = subjects.get(subject_id, "Unknown Subject")
            pdf_filename = f"{chapter_name}.pdf"
            pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
            dbg(f"\n[INFO] Chapter {chapter_id}: '{chapter_name}' | Subject='{subject_name}' | Class='{class_number}'")
            dbg(f"[INFO] PDF path: {pdf_path}")

            if not os.path.exists(pdf_path):
                dbg("[WARN] PDF file not found. Skipping this chapter.")
                continue

            t_pdf_open = time.time()
            doc = fitz.open(pdf_path)
            dbg(f"[DEBUG] Opened PDF in {time.time()-t_pdf_open:.2f}s | pages={len(doc)}")

            # Chapter number mapping
            chapter_num = CHAPTER_NUMBER_FALLBACK_MAP.get(pdf_filename)
            if not chapter_num:
                dbg(f"[ERROR] Filename '{pdf_filename}' not found in CHAPTER_NUMBER_FALLBACK_MAP. Skipping.")
                doc.close()
                continue
            dbg(f"[INFO] Chapter number from map: {chapter_num}")

            # Extract headings + text
            t_extract = time.time()
            headings, all_text = extract_text_and_headings_with_location(doc, chapter_num)
            dbg(f"[DEBUG] Extraction done in {time.time()-t_extract:.2f}s | headings={len(headings)} | blocks={len(all_text)}")

            # Map text to heading windows
            t_map = time.time()
            topic_content_map = map_text_to_headings(headings, all_text)
            dbg(f"[INFO] Topic map size: {len(topic_content_map)}")
            total_topics_mapped += len(topic_content_map)

            # Prepare and send updates
            update_count = 0
            sent_updates = 0
            for heading_full, content in topic_content_map.items():
                match = re.match(r"^\s*([\d\.]+)\s*[\s\.:;\-–]+(.*)$", heading_full)
                if not match:
                    dbg(f"[DEBUG] Skip heading with no number match: '{heading_full}'")
                    continue
                topic_num = match.group(1)
                title_part = match.group(2)
                content_len = len(content or "")
                dbg(f"    [DEBUG] Candidate update -> topic_number='{topic_num}', title='{title_part[:50]}', content_len={content_len}")
                if not content or content_len < 20:
                    dbg(f"    [DEBUG] Skipped (empty/short) for topic_number='{topic_num}'")
                    continue

                try:
                    cursor.execute(
                        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (content, chapter_id, topic_num)
                    )
                    sent_updates += 1
                except Exception as e:
                    dbg(f"[ERROR] Update exec failed for chapter_id={chapter_id} topic='{topic_num}': {e}")
                    dbg(traceback.format_exc())

            dbg(f"[DEBUG] Sent {sent_updates} UPDATE statements; committing...")
            try:
                conn.commit()
            except Exception as e:
                dbg(f"[ERROR] Commit failed: {e}")
                dbg(traceback.format_exc())
                conn.rollback()

            # Optional: check how many rows updated (Postgres rowcount is per execute; here we didn’t tally per-row)
            # If needed, re-run a diagnostic query to count non-empty full_text for this chapter.

            total_updates += sent_updates
            dbg(f"[INFO] Chapter summary: updates_sent={sent_updates}, headings_found={len(headings)}, topics_mapped={len(topic_content_map)}")

            doc.close()

        except Exception as e:
            dbg(f"[ERROR] Chapter loop error (chapter_id={chapter_id}): {e}")
            dbg(traceback.format_exc())
            try:
                doc.close()
            except Exception:
                pass
            continue

    dbg(f"\n[SUCCESS] Finished. Total chapters={len(chapters_to_process)}, total_updates_sent={total_updates}, total_topics_mapped={total_topics_mapped}")
    cursor.close()
    conn.close()
    dbg("[CLOSE] DB connection closed")

if __name__ == '__main__':
    main()
