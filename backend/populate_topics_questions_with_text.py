import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
from pdf2image import convert_from_path
import pytesseract

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\gemini_csv.csv"
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# --- Comprehensive Name Mapping (DB Chapter Name -> Actual PDF Filename without .pdf) ---
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

def run_ocr_on_pdf(pdf_path: str) -> str:
    log("    - Converting PDF to images and running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
        full_text = ""
        for i, image in enumerate(images):
            full_text += pytesseract.image_to_string(image) + "\n"
        log("    - OCR complete.")
        return full_text
    except Exception as e:
        log(f"    [ERROR] OCR process failed for {os.path.basename(pdf_path)}: {e}")
        return ""

def natural_sort_key(s):
    if s is None:
        return []
    parts = re.split(r'(\d+|\D+)', s)
    processed_parts = []
    for part in parts:
        if part.isdigit():
            processed_parts.append(int(part))
        elif part.isalpha():
            processed_parts.append(part.lower())
        else:
            processed_parts.append(part)
    return processed_parts

def extract_topics_and_questions(full_text: str, topics_from_csv: pd.DataFrame):
    extracted_topics = []
    csv_topics_info = sorted([
        {'id': row_id, 'topic_number': str(row['heading_number']), 'name': row['heading_text']}
        for row_id, row in topics_from_csv.iterrows()
    ], key=lambda x: natural_sort_key(x['topic_number']))

    found_topic_starts = {}
    
    log(f"    - Searching for {len(csv_topics_info)} topics in PDF text.")
    
    for i, topic_info in enumerate(csv_topics_info):
        topic_num = topic_info['topic_number']
        topic_name_from_csv = topic_info['name']
        
        patterns_to_try = [
            re.compile(r'^\s*' + re.escape(topic_num) + r'\s+' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*' + re.escape(topic_num) + r'\s*\.?\s*' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*' + re.escape(topic_num) + r'(\.?|\s+)' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*' + re.escape(topic_num) + r'(\.?|\s+)(.+?)$', re.MULTILINE | re.IGNORECASE), 
        ]
        
        found_match = None
        match_start_pos = -1
        matched_heading_text = ""
        
        for pattern in patterns_to_try:
            match = pattern.search(full_text)
            if match:
                if match_start_pos == -1 or match.start() < match_start_pos + len(matched_heading_text) + 500:
                    match_start_pos = match.start()
                    matched_heading_text = match.group(0).strip()
                    found_match = match
                    if re.escape(topic_name_from_csv).lower() in matched_heading_text.lower() and len(matched_heading_text.split()) > len(topic_num.split()):
                        break
        
        if found_match:
            found_topic_starts[topic_num] = (match_start_pos, matched_heading_text)
        else:
            log(f"        - WARNING: Heading '{topic_num} {topic_name_from_csv}' not found precisely in PDF. Skipping for now.")

    sorted_found_topics = sorted(
        [(num, pos, matched_text, next((info['id'] for info in csv_topics_info if info['topic_number'] == num), None), next((info['name'] for info in csv_topics_info if info['topic_number'] == num), None))
         for num, (pos, matched_text) in found_topic_starts.items()],
        key=lambda x: x[1]
    )

    for i, (topic_num, start_pos, matched_heading_text, original_csv_topic_id, original_csv_topic_name) in enumerate(sorted_found_topics):
        end_pos = len(full_text)
        if i + 1 < len(sorted_found_topics):
            end_pos = sorted_found_topics[i+1][1]

        content = full_text[start_pos:end_pos].strip()
        
        extracted_topics.append({
            'topic_number': topic_num,
            'title': original_csv_topic_name,
            'content': content
        })
        log(f"        - Extracted content for '{topic_num} {original_csv_topic_name}'.")

    questions = []
    exercise_markers = [r'EXERCISES', r'QUESTIONS', r'PRACTICE SET']
    exercises_match = None
    for marker in exercise_markers:
        exercises_match = re.search(marker, full_text, re.IGNORECASE)
        if exercises_match:
            break
            
    if exercises_match:
        exercises_text = full_text[exercises_match.start():]
        
        # --- THIS IS THE FIX ---
        # Changed the regex to use non-capturing groups (?:...)
        question_pattern = re.compile(r'^\s*(\d+(?:\.\d+)*\s*)\s*(.+?)(?=\n\s*\d+(?:\.\d+)*\s*|\Z)', re.MULTILINE | re.DOTALL)
        found_questions = question_pattern.findall(exercises_text)
        
        # Changed the loop to unpack only the two captured groups
        for q_num_raw, q_text in found_questions:
            questions.append({'question_number': q_num_raw.strip(), 'question_text': q_text.strip()})
        # ---------------------

        log(f"    - Found {len(questions)} potential questions.")
    else:
        log(f"    - No obvious 'EXERCISES' section found for question extraction.")
            
    return extracted_topics, questions

def update_database(cursor, chapter_id: int, topics: list, questions: list):
    log(f"    - Preparing to update {len(topics)} topics and {len(questions)} questions in the database.")
    
    for topic in topics:
        cursor.execute(
            "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
            (topic['content'], chapter_id, topic['topic_number'])
        )
    
    if questions:
        cursor.execute("DELETE FROM question_bank WHERE chapter_id = %s", (chapter_id,))
        for q in questions:
            cursor.execute(
                "INSERT INTO question_bank (chapter_id, question_number, question_text) VALUES (%s, %s, %s)",
                (chapter_id, q['question_number'], q['question_text'])
            )
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
        log(f"\n--- Processing Chapter: {chapter_name_db} ({subject_name_db} Class {class_number}) ---")

        folder_subject = subject_name_db
        if subject_name_db == 'Mathematics':
            folder_subject = 'Maths'
        
        mapped_pdf_filename_base = NAME_MAPPING.get(chapter_name_db, chapter_name_db)
        pdf_filename = f"{mapped_pdf_filename_base}.pdf"
        
        class_folder = f"Class {class_number}"
        folder_path = os.path.join(PDF_ROOT_FOLDER, folder_subject, class_folder)
        pdf_path = os.path.join(folder_path, pdf_filename)
        
        log(f"    [DEBUG] Looking for PDF at: {pdf_path}")

        if not os.path.exists(pdf_path):
            log(f"    [WARNING] PDF not found for '{chapter_name_db}' at '{pdf_path}'. Skipping chapter.")
            skipped_chapters_count += 1
            continue

        chapter_topics_df = master_df[master_df['chapter_file'] == f"{mapped_pdf_filename_base}.pdf"].copy()
        
        if chapter_topics_df.empty:
            log(f"    [WARNING] No topics found in CSV for chapter '{chapter_name_db}' (mapped to '{mapped_pdf_filename_base}.pdf'). Skipping.")
            skipped_chapters_count += 1
            continue

        full_chapter_text = run_ocr_on_pdf(pdf_path)
        
        if not full_chapter_text:
            log(f"    [ERROR] Failed to get text from '{pdf_filename}'. Skipping chapter.")
            skipped_chapters_count += 1
            continue
        
        topics_data, questions_data = extract_topics_and_questions(full_chapter_text, chapter_topics_df)
        
        if not topics_data:
            log(f"    [WARNING] No topics extracted from text for '{chapter_name_db}'. Skipping database update for topics.")
        
        update_database(cursor, chapter_id, topics_data, questions_data)
        conn.commit()
        log(f"    [SUCCESS] Finished processing and saving data for '{chapter_name_db}'.")
        processed_chapters_count += 1

    cursor.close()
    conn.close()
    log(f"\n[COMPLETE] Script finished. Processed {processed_chapters_count} chapters, skipped {skipped_chapters_count} chapters.")

if __name__ == '__main__':
    main()
