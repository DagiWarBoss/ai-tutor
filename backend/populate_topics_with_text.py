import os
import re
import psycopg2
from dotenv import load_dotenv
import pandas as pd
# Conditional imports for OCR - only if needed
from pdf2image import convert_from_path # UNCOMMENTED for OCR
import pytesseract # UNCOMMENTED for OCR

# ======= 1. VERIFY THESE PATHS FOR YOUR SYSTEM =======
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"
CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\gemini_csv.csv"

# ONLY UNCOMMENT AND SET THESE IF YOUR PDFs ARE SCANNED IMAGES AND NOT TEXT-SELECTABLE
POPPLER_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin" # UNCOMMENTED for OCR
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe" # UNCOMMENTED for OCR
# =======================================================

# --- Configuration ---
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# Only set if using OCR
if 'TESSERACT_PATH' in locals() and TESSERACT_PATH: # UNCOMMENTED for OCR
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# --- Comprehensive Name Mapping (DB Chapter Name -> Actual PDF Filename without .pdf) ---
# This is crucial for matching chapter names in your DB to actual PDF files on disk.
# Ensure this mapping is complete and accurate based on your actual filenames.
NAME_MAPPING = {
    # == CHEMISTRY ==
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
    'D And F Block': 'D And F Block', # Corrected based on last convo
    'Coordination Compounds': 'Coordination Compounds',
    'Haloalkanes And Haloarenes': 'Haloalkanes And Haloarenes',
    'Alcohol Phenols Ethers': 'Alcohol Phenols Ethers',
    'Aldehydes, Ketones And Carboxylic Acid': 'Aldehydes, Ketones And Carboxylic Acid', # Corrected based on last convo
    'Amines': 'Amines',
    'Biomolecules': 'Biomolecules',
    
    # == PHYSICS ==
    'Units And Measurements': 'Units And Measurements',
    'Motion In A Straight Line': 'Motion In A Straight Line', # Corrected based on last convo
    'Motion In A Plane': 'Motion In A Plane', # Corrected based on last convo
    'Laws Of Motion': 'Laws Of Motion',
    'Work Energy Power': 'Work Energy Power', # Corrected based on last convo
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
    'Electromagnetic Induction': 'Electromagnetic Induction', # Corrected based on last convo
    'Alternating Current': 'Alternating Current',
    'Electromagnetic Waves': 'Electromagnetic Waves',
    'Ray Optics': 'Ray Optics',
    'Wave Optics': 'Wave Optics', # Corrected based on last convo
    'Dual Nature Of Radiation And Matter': 'Dual Nature Of Radiation And Matter', # Corrected based on last convo
    'Atoms': 'Atoms',
    'Nuclei': 'Nuclei',
    'Semiconductor Electronics': 'Semiconductor Electronics',

    # == MATHS ==
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
    'Continuity And Differentiability': 'Continuity And Differentiability', # Corrected typo based on last convo
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
    """Fetches all chapters from the DB to create a name-to-ID map."""
    cursor.execute("SELECT name, id FROM chapters")
    return {name: chapter_id for name, chapter_id in cursor.fetchall()}

# --- OPTION A: For Text-Selectable PDFs (Recommended) ---
# import fitz # PyMuPDF
# def extract_text_from_pdf(pdf_path: str) -> str:
#     """Extracts text directly from a text-selectable PDF using PyMuPDF."""
#     log("    - Extracting text directly from PDF...")
#     try:
#         doc = fitz.open(pdf_path)
#         full_text = ""
#         for page in doc:
#             full_text += page.get_text() + "\n"
#         doc.close()
#         log("    - Direct text extraction complete.")
#         return full_text
#     except Exception as e:
#         log(f"    [ERROR] Direct text extraction failed for {os.path.basename(pdf_path)}: {e}")
#         return ""

# --- OPTION B: For Scanned PDFs (Uncomment and use if Option A fails) ---
from pdf2image import convert_from_path # UNCOMMENTED
import pytesseract # UNCOMMENTED
def run_ocr_on_pdf(pdf_path: str) -> str: # UNCOMMENTED
    """Performs OCR on every page of a PDF and returns the full text."""
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
    """
    Key for sorting strings in natural order (e.g., '1.10' comes after '1.2').
    Handles cases like A.1.1.
    """
    if s is None:
        return []
    # Split by dots and then by A or other non-digits to handle 'A.1.1' properly
    parts = re.split(r'(\d+|\D+)', s)
    processed_parts = []
    for part in parts:
        if part.isdigit():
            processed_parts.append(int(part))
        elif part.isalpha(): # For 'A' in 'A.1.1'
            processed_parts.append(part.lower())
        else:
            processed_parts.append(part) # For dots or other separators
    return processed_parts


def extract_topics_and_questions(full_text: str, topics_from_csv: pd.DataFrame):
    """
    Extracts topics and questions from the PDF text using the CSV as a guide.
    This version tries to match the full heading (number + text) more robustly.
    """
    extracted_topics = []
    
    # Prepare topics from CSV with their full expected headings and topic numbers
    # Ensure all topic_numbers are strings for consistent comparison
    csv_topics_info = sorted([
        {'id': row_id, 'topic_number': str(row['heading_number']), 'name': row['heading_text']}
        for row_id, row in topics_from_csv.iterrows()
    ], key=lambda x: natural_sort_key(x['topic_number']))

    # Store found topic start positions
    # Key: topic_number (e.g., "1.1"), Value: (start_index, full_matched_heading_text)
    found_topic_starts = {} 

    # Clean the full_text for matching (remove multiple spaces, newlines, normalize unicode)
    cleaned_full_text = re.sub(r'\s+', ' ', full_text).strip()

    log(f"    - Searching for {len(csv_topics_info)} topics in PDF text.")
    
    for i, topic_info in enumerate(csv_topics_info):
        topic_num = topic_info['topic_number']
        topic_name_from_csv = topic_info['name']

        # Construct possible heading patterns based on common formatting
        # 1. "1.1 Introduction"
        # 2. "1.1. Introduction" (with extra dot/space)
        # 3. "1.1.Introduction" (no space)
        # 4. "1.1" followed by some text (if name match is loose)
        # Using re.escape for topic_num and re.IGNORECASE for name matching
        patterns_to_try = [
            re.compile(r'^\s*' + re.escape(topic_num) + r'\s+' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*' + re.escape(topic_num) + r'\s*\.?\s*' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*' + re.escape(topic_num) + r'(\.?|\s+)' + re.escape(topic_name_from_csv) + r'\s*$', re.MULTILINE | re.IGNORECASE),
            # More flexible if name isn't perfectly matched: find number, then any text
            re.compile(r'^\s*' + re.escape(topic_num) + r'(\.?|\s+)(.+?)$', re.MULTILINE | re.IGNORECASE), 
        ]
        
        found_match = None
        match_start_pos = -1
        matched_heading_text = ""

        # Search for the heading in the full text, starting from the current search position
        # For simplicity, search from beginning for each, and then use sorting for extraction
        # This can be optimized by searching progressively from the previous topic's end
        
        for pattern in patterns_to_try:
            match = pattern.search(full_text) # Searches from the beginning each time
            if match:
                # Prioritize matches that are closer to the "correct" heading format
                # and are not too far from expected sequence
                if match_start_pos == -1 or match.start() < match_start_pos + len(matched_heading_text) + 500: # Heuristic to favor closer matches
                    match_start_pos = match.start()
                    matched_heading_text = match.group(0).strip()
                    found_match = match
                    # Break if a strong match is found (e.g., exact heading text)
                    if re.escape(topic_name_from_csv).lower() in matched_heading_text.lower() and len(matched_heading_text.split()) > len(topic_num.split()):
                        break # Found a good match, move on
        
        if found_match:
            found_topic_starts[topic_num] = (match_start_pos, matched_heading_text)
            # log(f"        - Found '{topic_num} {topic_name_from_csv}' at char {match_start_pos}")
        else:
            log(f"        - WARNING: Heading '{topic_num} {topic_name_from_csv}' not found precisely in PDF. Skipping for now.")
            # We won't add it to found_topic_starts, so it won't be processed.

    # Now, extract content based on sorted found headings
    # Convert dict to list of tuples and sort by start position
    sorted_found_topics = sorted(
        [(num, pos, matched_text, next((info['id'] for info in csv_topics_info if info['topic_number'] == num), None), next((info['name'] for info in csv_topics_info if info['topic_number'] == num), None))
         for num, (pos, matched_text) in found_topic_starts.items()],
        key=lambda x: x[1] # Sort by start position
    )

    for i, (topic_num, start_pos, matched_heading_text, original_csv_topic_id, original_csv_topic_name) in enumerate(sorted_found_topics):
        end_pos = len(full_text)
        if i + 1 < len(sorted_found_topics):
            # The next topic starts at the position of the (i+1)-th element in sorted_found_topics
            end_pos = sorted_found_topics[i+1][1]

        content = full_text[start_pos:end_pos].strip()

        # The content already starts with the matched heading text from the PDF.
        # This is usually desired. If you only want text *after* the heading,
        # you'd do content = content[len(matched_heading_text):].strip()
        
        extracted_topics.append({
            'topic_number': topic_num,
            'title': original_csv_topic_name, # Use original CSV title
            'content': content
        })
        log(f"        - Extracted content for '{topic_num} {original_csv_topic_name}'.")

    # Extract questions (remains similar to your original logic)
    questions = []
    # Try common markers for exercise sections
    exercise_markers = [r'EXERCISES', r'QUESTIONS', r'PRACTICE SET']
    exercises_match = None
    for marker in exercise_markers:
        exercises_match = re.search(marker, full_text, re.IGNORECASE)
        if exercises_match:
            break
            
    if exercises_match:
        exercises_text = full_text[exercises_match.start():]
        # This flexible regex finds a number, whitespace, and then the question text
        # It tries to be flexible with numbering (e.g., 1. or 1.1 or just 1)
        # and assumes a new question starts with a number.
        question_pattern = re.compile(r'^\s*(\d+(\.\d+)*\s*)\s*(.+?)(?=\n\s*\d+(\.\d+)*\s*|\Z)', re.MULTILINE | re.DOTALL)
        found_questions = question_pattern.findall(exercises_text)
        
        for q_num_raw, _, q_text in found_questions: # q_num_raw is like '1.1 ', _ is from inner group
            questions.append({'question_number': q_num_raw.strip(), 'question_text': q_text.strip()})
        log(f"    - Found {len(questions)} potential questions.")
    else:
        log(f"    - No obvious 'EXERCISES' section found for question extraction.")
            
    return extracted_topics, questions


def update_database(cursor, chapter_id: int, topics: list, questions: list):
    """Updates the database with the extracted topics and questions."""
    log(f"    - Preparing to update {len(topics)} topics and {len(questions)} questions in the database.")
    
    # Update topics
    for topic in topics:
        cursor.execute(
            "UPDATE topics SET full_text = %s WHERE chapter_id = %s AND topic_number = %s",
            (topic['content'], chapter_id, topic['topic_number'])
        )
    
    # Update questions (delete old ones first)
    # Make sure your question_bank table exists and matches these columns
    # CREATE TABLE question_bank (
    #     id SERIAL PRIMARY KEY,
    #     chapter_id INTEGER REFERENCES chapters(id),
    #     question_number TEXT,
    #     question_text TEXT,
    #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    # );
    
    if questions: # Only delete if there are questions to insert
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

    # It's better to iterate through chapters from the DB to ensure we process what's
    # actually in the DB and use the correct folder/name mappings.
    cursor.execute("""
        SELECT c.id, c.name, c.class_number, s.name as subject_name_db
        FROM chapters c
        JOIN subjects s ON c.subject_id = s.id
        ORDER BY s.name, c.class_number, c.name
    """)
    db_chapters = cursor.fetchall()

    for chapter_id, chapter_name_db, class_number, subject_name_db in db_chapters:
        log(f"\n--- Processing Chapter: {chapter_name_db} ({subject_name_db} Class {class_number}) ---")

        # Determine the actual folder name based on subject name
        folder_subject = subject_name_db
        if subject_name_db == 'Mathematics':
            folder_subject = 'Maths'
        
        # Use NAME_MAPPING to get the correct PDF filename from the DB chapter name
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

        # Filter the master CSV for topics belonging to this specific chapter
        # Use 'mapped_pdf_filename_base' for chapter_file to match CSV's "chapter_file" column
        # which probably has the original name from the PDF/CSV, not the DB's potentially corrected name.
        # This assumes your CSV's 'chapter_file' column still refers to the original filename string (e.g., 'D And F Block.pdf')
        # not the DB's `chapter.name` column (e.g., 'The d and f Block Elements').
        # If your CSV's chapter_file matches DB's chapter.name, use chapter_name_db instead of mapped_pdf_filename_base.
        
        # IMPORTANT: Decide which column in your CSV holds the chapter_file name to match
        # If gemini_csv.csv 'chapter_file' column contains "Some Basic Concepts Of Chemistry.pdf"
        # then use f"{mapped_pdf_filename_base}.pdf" for matching against it.
        # If it contains "Some Basic Concepts Of Chemistry" (without .pdf), adjust.
        chapter_topics_df = master_df[master_df['chapter_file'] == f"{mapped_pdf_filename_base}.pdf"].copy()
        
        if chapter_topics_df.empty:
            log(f"    [WARNING] No topics found in CSV for chapter '{chapter_name_db}' (mapped to '{mapped_pdf_filename_base}.pdf'). Skipping.")
            skipped_chapters_count += 1
            continue

        # Get the full text from the PDF (using PyMuPDF or OCR)
        # IF YOUR PDFs ARE SCANNED IMAGES, UNCOMMENT run_ocr_on_pdf AND COMMENT extract_text_from_pdf
        full_chapter_text = run_ocr_on_pdf(pdf_path) # For scanned PDFs
        # full_chapter_text = extract_text_from_pdf(pdf_path) # For text-selectable PDFs (Recommended)
        
        if not full_chapter_text:
            log(f"    [ERROR] Failed to get text from '{pdf_filename}'. Skipping chapter.")
            skipped_chapters_count += 1
            continue
        
        # Extract topics and questions from the chapter text
        topics_data, questions_data = extract_topics_and_questions(full_chapter_text, chapter_topics_df)
        
        if not topics_data:
            log(f"    [WARNING] No topics extracted from text for '{chapter_name_db}'. Skipping database update for topics.")
        
        # Update database with extracted data
        update_database(cursor, chapter_id, topics_data, questions_data)
        conn.commit() # Commit after each chapter's data is updated
        log(f"    [SUCCESS] Finished processing and saving data for '{chapter_name_db}'.")
        processed_chapters_count += 1

    cursor.close()
    conn.close()
    log(f"\n[COMPLETE] Script finished. Processed {processed_chapters_count} chapters, skipped {skipped_chapters_count} chapters.")

if __name__ == '__main__':
    main()
