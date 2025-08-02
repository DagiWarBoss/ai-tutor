import os
import fitz  # PyMuPDF
import psycopg2
import psycopg2.extras
import re
from dotenv import load_dotenv

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- SECURELY GET CREDENTIALS FROM ENVIRONMENT ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# --- CONFIGURATION ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TXT_CACHE_FOLDER = "txt_outputs"

# =================================================================
# FINALIZED CHAPTER ORDER MAPPING (Updated to match your exact filenames)
# =================================================================
CHAPTER_ORDER_MAPPING = {
    "Chemistry": {
        11: [
            "Some Basic Concepts Of Chemistry.pdf",
            "Structure Of Atom.pdf",
            "Classification Of Elements And Periodicity.pdf",
            "Chemical Bonding And Molecular Structure.pdf",
            "Thermodynamics.pdf",
            "Equilibrium.pdf",
            "Redox Reactions.pdf",
            "Organic Chemistry Basics.pdf",
            "Hydrocarbons.pdf"
        ],
        12: [
            "Solutions.pdf",
            "Electrochemistry.pdf",
            "Chemical Kinetics.pdf",
            "D And F Block.pdf",
            "Coordination Compounds.pdf",
            "Haloalkanes And Haloarenes.pdf",
            "Alcohol Phenols Ethers.pdf",
            "Aldehydes, Ketones And Carboxylic Acid.pdf",
            "Amines.pdf",
            "Biomolecules.pdf"
        ]
    },
    "Maths": {
        11: [
            "Sets.pdf",
            "Relations And Functions.pdf",
            "Trigonometric Functions.pdf",
            "Complex Numbers And Quadratic Equations.pdf",
            "Linear Inequalities.pdf",
            "Permutations And Combinations.pdf",
            "Binomial Theorem.pdf",
            "Sequences And Series.pdf",
            "Straight Lines.pdf",
            "Conic Sections.pdf",
            "3D Geometry.pdf", # Note: This is "Introduction to 3D Geometry"
            "Limits And Derivatives.pdf",
            "Statistics.pdf",
            "Probability.pdf"
        ],
        12: [
            "Relations And Functions.pdf",
            "Inverse Trigonometric Functions.pdf",
            "Matrices.pdf",
            "Determinants.pdf",
            "Contunuity And Differentiability.pdf",
            "Application Of Derivatives.pdf",
            "Integrals.pdf",
            "Application Of Integrals.pdf",
            "Differential Equations.pdf",
            "Vector Algebra.pdf",
            "3D Geometry.pdf",
            "Linear Programming.pdf",
            "Probability.pdf"
        ]
    },
    "Physics": {
        11: [
            "Units And Measurements.pdf",
            "Motion In A Straight Line.pdf",
            "Motion In A Plane.pdf",
            "Laws Of Motion.pdf",
            "Work Energy Power.pdf",
            "System Of Particles And Rotational Motion.pdf",
            "Gravitation.pdf",
            "Mechanical Properties Of Solids.pdf",
            "Mechanical Properties Of Fluids.pdf",
            "Thermal Properties Of Matter.pdf",
            "Thermodynamics.pdf",
            "Kinetic Theory.pdf",
            "Oscillations.pdf",
            "Waves.pdf"
        ],
        12: [
            "Electric Charges And Fields.pdf",
            "Electrostatic Potential And Capacitance.pdf",
            "Current Electricity.pdf",
            "Moving Charges And Magnetism.pdf",
            "Magnetism And Matter.pdf",
            "Electromagnetic Induction.pdf",
            "Alternating Current.pdf",
            "Electromagnetic Waves.pdf",
            "Ray Optics.pdf",
            "Wave Optics.pdf",
            "Dual Nature Of Radiation And Matter.pdf",
            "Atoms.pdf",
            "Nuclei.pdf",
            "SemiConductor Electronics.pdf"
        ]
    }
}

def extract_chapter_number_from_pdf(doc):
    """Scans the first page of a PDF for a 'Unit X' or 'Chapter X' pattern."""
    try:
        first_page_text = doc[0].get_text("text")
        # Look for patterns like "Unit 7" or "CHAPTER 12"
        match = re.search(r"(?:Unit|CHAPTER)\s*(\d+)", first_page_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"    - Warning: Error while extracting chapter number: {e}")
    return None

def extract_topics_from_pdf(doc):
    """A stricter topic extraction function that only captures numbered headings."""
    try:
        topics = []
        topic_pattern = re.compile(r"^\s*(\d+\.\d+[\.\d+]*)\s+([A-Z][A-Za-z\s,]{3,80})$", re.MULTILINE)
        for page_num in range(min(5, doc.page_count)):
            page_text = doc[page_num].get_text()
            matches = topic_pattern.findall(page_text)
            for match in matches:
                topics.append({"topic_number": match[0], "topic_name": match[1].strip()})
        
        seen_topics = set()
        unique_topics = []
        for topic in topics:
            if topic['topic_name'] not in seen_topics:
                seen_topics.add(topic['topic_name'])
                unique_topics.append(topic)
        return unique_topics
    except Exception as e:
        print(f"    - Error processing TOC for {os.path.basename(doc.name)}: {e}")
        return []

def get_full_text(doc, cache_path):
    """Gets full text, using a cache to speed up subsequent runs."""
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    print(f"    - Cache miss. Extracting text from PDF...")
    try:
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + " "
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"    - Saved text to cache: '{os.path.basename(cache_path)}'")
        return full_text.strip()
    except Exception as e:
        print(f"    - Error extracting full text from {os.path.basename(doc.name)}: {e}")
        return ""

def main():
    """Walks through the folder structure using the mapping and populates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Ensure .env file is correct.")
        return

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)
    txt_cache_full_path = os.path.join(script_dir, TXT_CACHE_FOLDER)

    try:
        with psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        ) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                # Iterate through our reliable mapping instead of os.listdir
                for subject_name, classes in CHAPTER_ORDER_MAPPING.items():
                    for class_level, chapter_files in classes.items():
                        if not chapter_files: continue

                        print(f"\n===== Processing Subject: '{subject_name}' (Class {class_level}) =====")
                        
                        upsert_subject_query = """
                            WITH ins AS (INSERT INTO subjects (name, class_level) VALUES (%s, %s) ON CONFLICT (name, class_level) DO NOTHING RETURNING id)
                            SELECT id FROM ins UNION ALL SELECT id FROM subjects WHERE name = %s AND class_level = %s LIMIT 1;
                        """
                        cur.execute(upsert_subject_query, (subject_name, class_level, subject_name, class_level))
                        subject_id = cur.fetchone()[0]
                        print(f"  -> Subject '{subject_name}' (Class {class_level}) has ID: {subject_id}")

                        for chapter_counter, filename in enumerate(chapter_files, 1):
                            chapter_name = os.path.splitext(filename)[0].strip()
                            
                            cur.execute("SELECT id FROM chapters WHERE subject_id = %s AND name = %s", (subject_id, chapter_name))
                            if cur.fetchone():
                                print(f"  -> Chapter '{chapter_name}' already exists. Skipping.")
                                continue

                            print(f"  -> Processing Chapter: {chapter_name}")

                            pdf_path = os.path.join(pdf_root_full_path, subject_name, f"Class {class_level}", filename)
                            if not os.path.exists(pdf_path):
                                print(f"    - ❌ ERROR: File not found at {pdf_path}. Please check filename. Skipping.")
                                continue

                            cache_path = os.path.join(txt_cache_full_path, subject_name, f"Class {class_level}", f"{chapter_name}.txt")
                            
                            try:
                                doc = fitz.open(pdf_path)
                                
                                # --- THIS IS THE NEW LOGIC ---
                                chapter_number = extract_chapter_number_from_pdf(doc)
                                if chapter_number is None:
                                    print(f"    - Warning: Could not find real chapter number. Using fallback counter: {chapter_counter}")
                                    chapter_number = chapter_counter
                                else:
                                    print(f"    - Success: Found real chapter number: {chapter_number}")

                                full_chapter_text = get_full_text(doc, cache_path)
                                topics_data = extract_topics_from_pdf(doc)
                                doc.close()

                                cur.execute(
                                    "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                    (subject_id, chapter_number, chapter_name, full_chapter_text),
                                )
                                chapter_id = cur.fetchone()[0]

                                if topics_data:
                                    print(f"    - Found {len(topics_data)} clean topics. Inserting...")
                                    topic_values = [(chapter_id, topic['topic_number'], topic['topic_name']) for topic in topics_data]
                                    psycopg2.extras.execute_values(cur, "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s", topic_values)
                            except Exception as e:
                                print(f"  ❌ CRITICAL ERROR processing file {filename}: {e}")
                                        
            print("\n✅ All data has been successfully inserted and committed.")

    except FileNotFoundError:
        print(f"❌ Error: The root folder '{pdf_root_full_path}' was not found. Please check the path.")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print("  The transaction has been rolled back.")
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
