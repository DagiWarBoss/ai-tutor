import os
import fitz  # PyMuPDF
import re
from dotenv import load_dotenv
import psycopg2
from collections import Counter
import threading

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
PAGE_PROCESS_TIMEOUT = 5  # Seconds to wait before skipping a complex page

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

def get_page_data_with_timeout(page, output_type, timeout=5, **kwargs):
    """
    Calls page.get_text() with a timeout. Returns the result, or None if it times out.
    """
    result = [None]
    def target():
        try:
            # --- THIS IS THE FIX ---
            # Call get_text with output_type as a positional argument
            result[0] = page.get_text(output_type, **kwargs)
        except Exception as e:
            result[0] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        return None  # Timed out
    
    if isinstance(result[0], Exception):
        # Re-raise the actual exception if one occurred in the thread
        raise result[0]
        
    return result[0]

def get_most_common_font_info(doc):
    font_counts = Counter()
    for page_num, page in enumerate(doc):
        if page_num > 5: break
        blocks_data = get_page_data_with_timeout(page, "dict", timeout=PAGE_PROCESS_TIMEOUT)
        if blocks_data is None:
            print(f"    [WARNING] Font analysis on page {page_num+1} timed out.")
            continue
        
        blocks = blocks_data["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        key = (round(s["size"]), "bold" in s["font"].lower())
                        font_counts[key] += 1
    if not font_counts: return (10.0, False)
    return font_counts.most_common(1)[0][0]

def extract_text_and_headings_with_location(doc, chapter_number):
    body_font_size, body_is_bold = get_most_common_font_info(doc)
    pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-–]+([A-Za-z].*)$")
    headings, all_text_blocks = [], []

    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        top_margin, bottom_margin = page_height * 0.10, page_height * 0.90

        blocks = get_page_data_with_timeout(page, "blocks", timeout=PAGE_PROCESS_TIMEOUT, sort=True)
        styled_blocks_data = get_page_data_with_timeout(page, "dict", timeout=PAGE_PROCESS_TIMEOUT, flags=fitz.TEXT_INHIBIT_SPACES)

        if blocks is None or styled_blocks_data is None:
            print(f"    [WARNING] Page {page_num+1} is too complex and timed out. Skipping page content.")
            continue
        
        for b in blocks:
            x0, y0, x1, y1, block_text_raw, _, _ = b
            block_text = block_text_raw.strip().replace('\n', ' ')
            if block_text and (y0 < top_margin or y1 > bottom_margin): continue
            if block_text: all_text_blocks.append({'text': block_text, 'page': page_num, 'y': y0})
        
        for b in styled_blocks_data["blocks"]:
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    if pat.match(line_text):
                        first_span = l["spans"][0]
                        span_size = round(first_span["size"])
                        span_is_bold = "bold" in first_span["font"].lower()
                        is_heading = (span_size > body_font_size) or (span_is_bold and not body_is_bold)
                        if is_heading:
                            headings.append({'text': line_text, 'page': page_num, 'y': b['bbox'][1]})
                            
    unique_headings = list({h['text']: h for h in headings}.values())
    return unique_headings, all_text_blocks

def map_text_to_headings(headings, all_text_blocks):
    topic_content = {}
    sorted_headings = sorted(headings, key=lambda h: (h['page'], h['y']))
    for i, heading in enumerate(sorted_headings):
        content = []
        start_page, start_y = heading['page'], heading['y']
        end_page = sorted_headings[i+1]['page'] if i + 1 < len(sorted_headings) else float('inf')
        end_y = sorted_headings[i+1]['y'] if i + 1 < len(sorted_headings) else float('inf')
        for block in all_text_blocks:
            is_after_start = block['page'] > start_page or (block['page'] == start_page and block['y'] > start_y)
            is_before_end = block['page'] < end_page or (block['page'] == end_page and block['y'] < end_y)
            if is_after_start and is_before_end:
                is_a_heading = any(h['text'] == block['text'] for h in sorted_headings)
                if not is_a_heading:
                    content.append(block['text'])
        topic_content[heading['text']] = "\n".join(content)
    return topic_content

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters")
    chapters_to_process = cursor.fetchall()
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name = subjects.get(subject_id, "Unknown Subject")
        pdf_filename = f"{chapter_name}.pdf"
        pdf_path = os.path.join(PDF_ROOT_FOLDER, subject_name, class_number, pdf_filename)
        
        print(f"\nProcessing: {pdf_path}")
        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF file not found. Skipping.")
            continue
        doc = fitz.open(pdf_path)
        
        chapter_num = CHAPTER_NUMBER_FALLBACK_MAP.get(pdf_filename)
        if chapter_num:
            print(f"  [INFO] Using Chapter Number from map: {chapter_num}")
            headings, all_text = extract_text_and_headings_with_location(doc, chapter_num)
            topic_content_map = map_text_to_headings(headings, all_text)
            print(f"  - Found {len(topic_content_map)} topics with text to update.")
            for heading_full, content in topic_content_map.items():
                match = re.match(r"^\s*([\d\.]+)\s*[\s\.:;\-–]+(.*)$", heading_full)
                if match and content:
                    topic_num = match.group(1)
                    cursor.execute(
                        "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
                        (content, chapter_id, topic_num)
                    )
        else:
            print(f"  [ERROR] Filename '{pdf_filename}' not found in the hardcoded map. Skipping.")
        doc.close()
    
    conn.commit()
    cursor.close()
    conn.close()
    print("\n[SUCCESS] Script finished processing all chapters.")

if __name__ == '__main__':
    main()