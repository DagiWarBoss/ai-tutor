import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
import psycopg2
import re

# --- Configuration ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
load_dotenv()
SUPABASE_URI = os.getenv("SUPABASE_CONNECTION_STRING")

# --- Comprehensive Name Mapping (DB Name -> Filename without .pdf) ---
# Based on your screenshots and previous CSV structure.
NAME_MAPPING = {
    # == CHEMISTRY ==
    # Class 11
    'Some Basic Concepts Of Chemistry': 'Some Basic Concepts Of Chemistry',
    'Structure Of Atom': 'Structure Of Atom',
    'Classification Of Elements And Periodicity': 'Classification Of Elements And Periodicity',
    'Chemical Bonding And Molecular Structure': 'Chemical Bonding And Molecular Structure',
    'Thermodynamics': 'Thermodynamics',
    'Equilibrium': 'Equilibrium',
    'Redox Reactions': 'Redox Reactions',
    'Organic Chemistry Basics': 'Organic Chemistry Basics',
    'Hydrocarbons': 'Hydrocarbons',
    # Class 12
    'Solutions': 'Solutions',
    'Electrochemistry': 'Electrochemistry',
    'Chemical Kinetics': 'Chemical Kinetics',
    'D And F Block': 'D And F Block',
    'Coordination Compounds': 'Coordination Compounds',
    'Haloalkanes And Haloarenes': 'Haloalkanes And Haloarenes',
    'Alcohol Phenols Ethers': 'Alcohol Phenols Ethers',
    'Aldehydes Ketones And Carboxylic Acid': 'Aldehydes, Ketones And Carboxylic Acid', # Note the comma in your screenshot file
    'Amines': 'Amines',
    'Biomolecules': 'Biomolecules',
    
    # == PHYSICS ==
    # Class 11
    'Units And Measurements': 'Units And Measurements',
    'Motion-In-A-Straight-Line': 'Motion In A Straight Line',
    'Motion-In-A-Plane': 'Motion In A Plane',
    'Laws Of Motion': 'Laws Of Motion',
    'Work Energy Power': 'Work Energy Power',
    'System Of Particles And Rotational Motion': 'System Of Particles And Rotational Motion',
    'Gravitation': 'Gravitation',
    'Mechanical Properties Of Solids': 'Mechanical Properties Of Solids',
    'Mechanical Properties Of Fluids': 'Mechanical Properties Of Fluids',
    'Thermal Properties Of Matter': 'Thermal Properties Of Matter',
    'Thermodynamics': 'Thermodynamics', # Note: Name exists in Chem too
    'Kinetic Theory': 'Kinetic Theory',
    'Oscillations': 'Oscillations',
    'Waves': 'Waves',
    # Class 12
    'Electric Charges And Fields': 'Electric Charges And Fields',
    'Electrostatic Potential And Capacitance': 'Electrostatic Potential And Capacitance',
    'Current Electricity': 'Current Electricity',
    'Moving Charges And Magnetism': 'Moving Charges And Magnetism',
    'Magnetism And Matter': 'Magnetism And Matter',
    'Electromagnetic-Induction': 'Electromagnetic Induction',
    'Alternating Current': 'Alternating Current',
    'Electromagnetic Waves': 'Electromagnetic Waves',
    'Ray Optics': 'Ray Optics',
    'Wave-Optics': 'Wave Optics',
    'Dual-Nature-Of-Radiation-And-Matter': 'Dual Nature Of Radiation And Matter',
    'Atoms': 'Atoms',
    'Nuclei': 'Nuclei',
    'Semiconductor Electronics': 'Semiconductor Electronics',

    # == MATHS (from previous fix) ==
    # Class 11
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
    # Class 12
    'Application Of Derivatives': 'Application Of Derivatives',
    'Application Of Integrals': 'Application Of Integrals',
    'Contunuity And Differentiability': 'Contunuity And Differentiability',
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

def extract_full_text_from_pdf(pdf_path):
    print(f"    - Reading file: {os.path.basename(pdf_path)}")
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
        return full_text
    except Exception as e:
        print(f"    [WARNING] Could not extract text from {os.path.basename(pdf_path)}: {e}")
        return None

def main():
    if not SUPABASE_URI:
        print("[ERROR] SUPABASE_CONNECTION_STRING not found in .env file.")
        return
        
    try:
        conn = psycopg2.connect(SUPABASE_URI)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to Supabase: {e}")
        return

    # 1. Get all subjects to help build file paths
    cursor.execute("SELECT id, name FROM subjects")
    subjects = {sub_id: sub_name for sub_id, sub_name in cursor.fetchall()}

    # 2. Find ALL chapters from ALL subjects that are MISSING full_text
    cursor.execute("SELECT id, name, class_number, subject_id FROM chapters WHERE full_text IS NULL")
    chapters_to_process = cursor.fetchall()
    
    if not chapters_to_process:
        print("[INFO] All chapters already have their full text populated. Nothing to do.")
        conn.close()
        return

    print(f"[INFO] Found {len(chapters_to_process)} chapters that need their full text extracted.")

    # 3. Loop through each chapter, extract its text, and update the database
    for chapter_id, chapter_name, class_number, subject_id in chapters_to_process:
        subject_name_from_db = subjects.get(subject_id)
        
        # --- THIS IS THE FIX for folder names ---
        if subject_name_from_db == 'Mathematics':
            folder_subject = 'Maths'
        else:
            folder_subject = subject_name_from_db # Works for 'Physics' and 'Chemistry'
        # ----------------------------------------

        # Use manual mapping if available, otherwise just fall back to the raw DB name
        mapped_name = NAME_MAPPING.get(chapter_name, chapter_name)
        pdf_filename = f"{mapped_name}.pdf"
        class_folder = f"Class {class_number}"
        folder_path = os.path.join(PDF_ROOT_FOLDER, folder_subject, class_folder)
        pdf_path = os.path.join(folder_path, pdf_filename)
        
        print(f"\nProcessing Chapter ID {chapter_id}: {chapter_name} ({subject_name_from_db})")
        print(f"  [DEBUG] Trying PDF path: {pdf_path}")

        if not os.path.exists(folder_path):
            print(f"  [WARNING] FOLDER NOT FOUND: '{folder_path}'. Skipping.")
            continue
            
        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF FILE NOT FOUND for chapter '{chapter_name}'. Skipping.")
            continue
            
        full_text = extract_full_text_from_pdf(pdf_path)
        
        if full_text:
            cursor.execute(
                "UPDATE chapters SET full_text = %s WHERE id = %s",
                (full_text, chapter_id)
            )
            print(f"  [SUCCESS] Successfully updated chapter '{chapter_name}' with its full text.")

    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n[COMPLETE] Finished processing all chapters.")

if __name__ == '__main__':
    main()
