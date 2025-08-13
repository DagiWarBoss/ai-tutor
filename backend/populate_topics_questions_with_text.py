import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
from pdf2image import convert_from_path
import pytesseract

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

# --- Comprehensive Name Mapping ---
NAME_MAPPING = {
    'Some Basic Concepts Of Chemistry': 'Some Basic Concepts Of Chemistry',
    'Structure Of Atom': 'Structure Of Atom',
    'Classification Of Elements And Periodicity': 'Classification Of Elements And Periodicity',
    'Chemical Bonding And Molecular Structure': 'Chemical Bonding And Molecular Structure',
    'Thermodynamics': 'Thermodynamics',
    'Equilibrium': 'Equilibrium',
    'Redox Reactions': 'Redox Reactions',
    'Organic Chemistry Basics': 'Organic Chemistry Basics',
    'Hydrocarbons': 'Hydrocarbons',
    'Solutions': 'Solutions',
    'Electrochemistry': 'Electrochemistry',
    'Chemical Kinetics': 'Chemical Kinetics',
    'D And F Block': 'D And F Block',
    'Coordination Compounds': 'Coordination Compounds',
    'Haloalkanes And Haloarenes': 'Haloalkanes And Haloarenes',
    'Alcohol Phenols Ethers': 'Alcohol Phenols Ethers',
    'Aldehydes, Ketones And Carboxylic Acid': 'Aldehydes, Ketones And Carboxylic Acid',
    'Amines': 'Amines',
    'Biomolecules': 'Biomolecules',
    'Units And Measurements': 'Units And Measurements',
    'Motion In A Straight Line': 'Motion In A Straight Line',
    'Motion In A Plane': 'Motion In A Plane',
    'Laws Of Motion': 'Laws Of Motion',
    'Work Energy Power': 'Work Energy Power',
    'System Of Particles And Rotational Motion': 'System Of Particles And Rotational Motion',
    'Gravitation': 'Gravitation',
    'Mechanical Properties Of Solids': 'Mechanical Properties Of Solids',
    'Mechanical Properties Of Fluids': 'Mechanical Properties Of Fluids',
    'Thermal Properties Of Matter': 'Thermal Properties Of Matter',
    'Kinetic Theory': 'Kinetic Theory',
    'Oscillations': 'Oscillations',
    'Waves': 'Waves',
    'Electric Charges And Fields': 'Electric Charges And Fields',
    'Electrostatic Potential And Capacitance': 'Electrostatic Potential And Capacitance',
    'Current Electricity': 'Current Electricity',
    'Moving Charges And Magnetism': 'Moving Charges And Magnetism',
    'Magnetism And Matter': 'Magnetism And Matter',
    'Electromagnetic Induction': 'Electromagnetic Induction',
    'Alternating Current': 'Alternating Current',
    'Electromagnetic Waves': 'Electromagnetic Waves',
    'Ray Optics': 'Ray Optics',
    'Wave Optics': 'Wave Optics',
    'Dual Nature Of Radiation And Matter': 'Dual Nature Of Radiation And Matter',
    'Atoms': 'Atoms',
    'Nuclei': 'Nuclei',
    'Semiconductor Electronics': 'Semiconductor Electronics',
    'Binomial Theorem': 'Binomial Theorem',
    'Complex Numbers And Quadratic Equations': 'Complex Numbers And Quadratic Equations',
    'Conic Sections': 'Conic Sections',
    'Introduction to Three Dimensional Geometry': 'Introduction to Three Dimensional Geometry',
    'Limits And Derivatives': 'Limits And Derivatives',
    'Linear Inequalities': 'Linear Inequalities',
    'Permutations And Combinations': 'Permutations And Combinations',
    'Probability': 'Probability',
    'Relations And Functions': 'Relations And Functions',
    'Sequences And Series': 'Sequences And Series',
    'Sets': 'Sets',
    'Statistics': 'Statistics',
    'Straight Lines': 'Straight Lines',
    'Trigonometric Functions': 'Trigonometric Functions',
    'Application Of Derivatives': 'Application Of Derivatives',
    'Application Of Integrals': 'Application Of Integrals',
    'Continuity And Differentiability': 'Continuity And Differentiability',
    'Determinants': 'Determinants',
    'Differential Equations': 'Differential Equations',
    'Infinite Series': 'Infinite Series',
    'Integrals': 'Integrals',
    'Inverse Trigonometric Functions': 'Inverse Trigonometric Functions',
    'Linear Programming': 'Linear Programming',
    'Matrices': 'Matrices',
    'Proofs In Mathematics': 'Proofs In Mathematics',
    'Three Dimensional Geometry': 'Three Dimensional Geometry',
    'Vector Algebra': 'Vector Algebra'
}

def log(msg: str):
    print(msg, flush=True)

def get_chapter_map_from_db(cursor):
    cursor.execute("SELECT name, id FROM chapters")
    return {name: chapter_id for name, chapter_id in cursor.fetchall()}

def clean_ocr_text(text: str) -> str:
    # Simplified: Focus on basics to avoid over-correction
    text = re.sub(r'[^\S\r\n]+', ' ', text)  # Replace multiple spaces/tabs with single space
    text = re.sub(r'\s*\n\s*', '\n', text)   # Normalize newlines
    return text.strip()

def get_text_from_pdf_with_caching(pdf_path: str) -> str:
    pdf_filename = os.path.basename(pdf_path)
    cache_filepath = os.path.join(OCR_CACHE_FOLDER, pdf_filename + ".txt")

    if os.path.exists(cache_filepath):
        log(f"    - Found cached OCR text for '{pdf_filename}'. Reading from cache.")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()

    log("    - No cache found. Converting PDF to images and running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
        full_text = ""
        for i, image in enumerate(images):
            full_text += pytesseract.image_to_string(image, config='--psm 3') + "\n"  # Improved layout detection
        log("    - OCR complete.")
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        log(f"    - Saved new OCR text to cache: '{os.path.basename(cache_filepath)}'")
        return full_text
    except Exception as e:
        log(f"    [ERROR] OCR process failed for {pdf_filename}: {e}")
        return ""

def extract_topics_and_questions(ocr_text: str, topics_from_csv: pd.DataFrame):
    # Clean the OCR text first
    ocr_text = clean_ocr_text(ocr_text)
    
    extracted_topics = []
    
    # Refined regex: Flexible for sublevels, requires space or end after number to avoid over-matching
    topic_numbers_escaped = [re.escape(str(num)).replace('\\.', r'(?:\.|\s|\-)?') for num in topics_from_csv['heading_number']]
    heading_pattern = re.compile(r'(?m)^\s*(' + '|'.join(topic_numbers_escaped) + r')(?:\s|\.|$)', re.IGNORECASE)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {}
    text_length = len(ocr_text)
    for match in matches:
        # Normalize matched number (remove spaces, fix dashes)
        cleaned_num = re.sub(r'\s+', '', match.group(1)).replace('-', '.')
        pos = match.start()
        # Filter: Ignore matches in likely exercise sections (last 20% of text)
        if pos < text_length * 0.8:
            if cleaned_num not in topic_locations:  # Avoid duplicates
                topic_locations[cleaned_num] = pos
                log(f"    - Matched heading: {cleaned_num} at position {pos}")
    
    # Log expected vs found
    expected_topics = set(topics_from_csv['heading_number'].astype(str))
    found_topics = set(topic_locations.keys())
    missing_topics = expected_topics - found_topics
    log(f"    - Found {len(topic_locations)} of {len(topics_from_csv)} topic headings in the PDF text.")
    if missing_topics:
        log(f"    - Missing topics: {', '.join(sorted(missing_topics))} (check OCR for artifacts or adjust regex).")
        for miss in list(missing_topics)[:3]:  # Limit to 3 for brevity
            miss_pos = ocr_text.find(miss)
            if miss_pos != -1:
                snippet = ocr_text[max(0, miss_pos-50):miss_pos+50].replace('\n', ' ')
                log(f"      - Snippet around missing '{miss}': ...{snippet}...")

    # Extract content for found topics
    sorted_locations = sorted(topic_locations.items(), key=lambda x: x[1])
    for i, (topic_num, start_pos) in enumerate(sorted_locations):
        end_pos = sorted_locations[i+1][1] if i+1 < len(sorted_locations) else len(ocr_text)
        content = ocr_text[start_pos:end_pos].strip()
        title = topics_from_csv[topics_from_csv['heading_number'] == topic_num]['heading_text'].values[0] if not topics_from_csv[topics_from_csv['heading_number'] == topic_num].empty else ''
        extracted_topics.append({'topic_number': topic_num, 'title': title, 'content': content})
    
    # Improved fallback: Scan for missing subtopics within each extracted topic's content
    for topic in extracted_topics[:]:  # Copy to avoid modification issues
        content = topic['content']
        sub_matches = heading_pattern.finditer(content)
        for sub_match in sub_matches:
            sub_cleaned = re.sub(r'\s+', '', sub_match.group(1)).replace('-', '.')
            if sub_cleaned in missing_topics and sub_cleaned not in topic_locations:
                sub_start = sub_match.start() + topic_locations[topic['topic_number']]
                topic_locations[sub_cleaned] = sub_start
                sub_end = len(ocr_text)  # Default to end; adjust if next found
                for next_num, next_pos in sorted_locations:
                    if next_pos > sub_start:
                        sub_end = next_pos
                        break
                sub_content = ocr_text[sub_start:sub_end].strip()
                sub_title = topics_from_csv[topics_from_csv['heading_number'] == sub_cleaned]['heading_text'].values[0] if not topics_from_csv[topics_from_csv['heading_number'] == sub_cleaned].empty else ''
                extracted_topics.append({'topic_number': sub_cleaned, 'title': sub_title, 'content': sub_content})
                log(f"    - Fallback match for subtopic: {sub_cleaned} at position {sub_start}")
                missing_topics.remove(sub_cleaned)  # Update missing set

    # (Question extraction unchanged)
    questions = []
    exercise_markers = [r'EXERCISES', r'QUESTIONS', 'PROBLEMS']
    exercises_match = None
    for marker in exercise_markers:
        exercises_match = re.search(marker, ocr_text, re.IGNORECASE)
        if exercises_match:
            break
            
    if exercises_match:
        exercises_text = ocr_text[exercises_match.start():]
        question_pattern = re.compile(
            r'^\s*(\d+(?:\.\d+)?)[\.\)]\s*(.+?)(?=\n\s*\d+(?:\.\d+)?[\.\)]|\nEXERCISES|\nQUESTIONS|\Z)',
            re.MULTILINE | re.DOTALL
        )
        found_questions = question_pattern.findall(exercises_text)
        
        log(f"    - Found {len(found_questions)} potential questions.")
        
        for q_num, q_text in found_questions:
            if q_text.strip():
                questions.append({'question_number': q_num.strip(), 'question_text': q_text.strip()})
    else:
        log(f"    - No obvious 'EXERCISES' or 'QUESTIONS' section found.")
            
    return extracted_topics, questions

def update_database(cursor, chapter_id: int, topics: list, questions: list):
    log(f"    - Preparing to update {len(topics)} topics and {len(questions)} questions in the database.")
    for topic in topics:
        cursor.execute("UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s", (topic['content'], chapter_id, topic['topic_number']))
    if questions:
        cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
        for q in questions:
            cursor.execute("INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)", (chapter_id, q['question_number'], q['question_text']))
    log(f"    - Database update commands sent.")

def main():
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
        log("[INFO] Successfully connected to Supabase.")
    except Exception as e:
        log(f"[ERROR] Could not connect to Supabase: {e}")
        return
        
    try:
        master_df = pd.read_csv(CSV_PATH, dtype=str).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        log(f"[INFO] Loaded master topic list from {CSV_PATH}.")
    except FileNotFoundError:
        log(f"[ERROR] CSV file not found at: {CSV_PATH}")
        return

    chapter_map = get_chapter_map_from_db(cursor)
    processed_chapters_count = 0
    skipped_chapters_count = 0

    cursor.execute("""
        SELECT c.id, c.name, c.class_number, s.name as subject_name_db
        FROM chapters c
        JOIN subjects s ON c.subject_id = s.id
        ORDER BY s.name, c.class_number, c.name
    """)
    db_chapters = cursor.fetchall()

    for chapter_id, chapter_name_db, class_number, subject_name_db in db_chapters:
        # For testing: Uncomment to process only one chapter (e.g., the problematic one)
        # if chapter_name_db != 'Chemical Bonding And Molecular Structure': continue
        
        log(f"\n--- Processing Chapter: {chapter_name_db} ({subject_name_db} Class {class_number}) ---")
        folder_subject = 'Maths' if subject_name_db == 'Mathematics' else subject_name_db
        mapped_pdf_filename_base = NAME_MAPPING.get(chapter_name_db, chapter_name_db)
        pdf_filename = f"{mapped_pdf_filename_base}.pdf"
        class_folder = f"Class {class_number}"
        folder_path = os.path.join(PDF_ROOT_FOLDER, folder_subject, class_folder)
        pdf_path = os.path.join(folder_path, pdf_filename)
        
        log(f"    [DEBUG] Looking for PDF at: {pdf_path}")
        if not os.path.exists(pdf_path):
            log(f"    [WARNING] PDF not found for '{chapter_name_db}'. Skipping chapter.")
            skipped_chapters_count += 1
            continue

        chapter_topics_df = master_df[master_df['chapter_file'] == pdf_filename].copy()
        if chapter_topics_df.empty:
            log(f"    [WARNING] No topics found in CSV for chapter '{pdf_filename}'. Skipping.")
            skipped_chapters_count += 1
            continue

        full_chapter_text = get_text_from_pdf_with_caching(pdf_path)
        if not full_chapter_text:
            log(f"    [ERROR] Failed to get text from '{pdf_filename}'. Skipping.")
            skipped_chapters_count += 1
            continue
        
        topics_data, questions_data = extract_topics_and_questions(full_chapter_text, chapter_topics_df)
        
        if not topics_data and not questions_data:
            log(f"    [WARNING] No topics or questions extracted from text. Skipping database update.")
        else:
            update_database(cursor, chapter_id, topics_data, questions_data)
            conn.commit()
            log(f"    [SUCCESS] Finished processing and saving data for '{chapter_name_db}'.")
            processed_chapters_count += 1

    cursor.close()
    conn.close()
    log(f"\n[COMPLETE] Script finished. Processed {processed_chapters_count} chapters, skipped {skipped_chapters_count} chapters.")

if __name__ == '__main__':
    main()
