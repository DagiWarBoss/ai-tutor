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
# --- THIS IS THE NEW CACHE FOLDER ---
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Create the cache directory if it doesn't exist
os.makedirs(OCR_CACHE_FOLDER, exist_ok=True)

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

def get_text_from_pdf_with_caching(pdf_path: str) -> str:
    """
    Gets text from a PDF. First checks a cache folder. If not cached,
    runs OCR and saves the result to the cache for future runs.
    """
    pdf_filename = os.path.basename(pdf_path)
    cache_filepath = os.path.join(OCR_CACHE_FOLDER, pdf_filename + ".txt")

    # Step 1: Check if the OCR text is already cached
    if os.path.exists(cache_filepath):
        log(f"    - Found cached OCR text for '{pdf_filename}'. Reading from cache.")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()

    # Step 2: If not cached, run the expensive OCR process
    log("    - No cache found. Converting PDF to images and running OCR...")
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
        full_text = ""
        for i, image in enumerate(images):
            full_text += pytesseract.image_to_string(image) + "\n"
        log("    - OCR complete.")

        # Step 3: Save the newly generated text to the cache
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        log(f"    - Saved new OCR text to cache: '{os.path.basename(cache_filepath)}'")

        return full_text
    except Exception as e:
        log(f"    [ERROR] OCR process failed for {pdf_filename}: {e}")
        return ""

def extract_topics_and_questions(ocr_text: str, topics_from_csv: pd.DataFrame):
    extracted_topics = []
    
    topic_numbers = [re.escape(str(num)) for num in topics_from_csv['heading_number']]
    heading_pattern = re.compile(r'^(%s)\s+' % '|'.join(topic_numbers), re.MULTILINE)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {match.group(1): match.start() for match in matches}

    log(f"    - Found {len(topic_locations)} of {len(topics_from_csv)} topic headings in the PDF text.")

    for index, row in topics_from_csv.iterrows():
        topic_num = str(row['heading_number'])
        start_pos = topic_locations.get(topic_num)
        
        if start_pos is not None:
            end_pos = len(ocr_text)
            for next_num, next_pos in topic_locations.items():
                if next_pos > start_pos and next_pos < end_pos:
                    end_pos = next_pos
            content = ocr_text[start_pos:end_pos].strip()
            extracted_topics.append({'topic_number': topic_num, 'title': row['heading_text'], 'content': content})

    questions = []
    exercise_markers = [r'EXERCISES', r'QUESTIONS', 'PROBLEMS']
    exercises_match = None
    for marker in exercise_markers:
        exercises_match = re.search(marker, ocr_text, re.IGNORECASE)
        if exercises_match:
            break
            
    if exercises_match:
        exercises_text = ocr_text[exercises_match.start():]
        question_start_pattern = re.compile(r'^\s*(\d+(\.\d+)?)\s*[\.\)]\s*', re.MULTILINE)
        question_matches = list(question_start_pattern.finditer(exercises_text))
        log(f"    - Found {len(question_matches)} potential question starts.")
        for i, match in enumerate(question_matches):
            q_num = match.group(1)
            start_pos = match.end()
            end_pos = len(exercises_text)
            if i + 1 < len(question_matches):
                end_pos = question_matches[i+1].start()
            q_text = exercises_text[start_pos:end_pos].strip()
            if q_text:
                questions.append({'question_number': q_num, 'question_text': q_text})
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

        # This now uses the caching function
        full_chapter_text = get_text_from_pdf_with_caching(pdf_path)
        
        if not full_chapter_text:
            log(f"    [ERROR] Failed to get text from '{pdf_filename}'. Skipping chapter.")
            skipped_chapters_count += 1
            continue
        
        topics_data, questions_data = extract_topics_and_questions(full_chapter_text, chapter_topics_df)
        
        if not topics_data and not questions_data:
            log(f"    [WARNING] No topics or questions extracted from text for '{chapter_name_db}'. Skipping database update.")
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
