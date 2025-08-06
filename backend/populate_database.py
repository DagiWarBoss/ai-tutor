import os
import fitz  # PyMuPDF
import psycopg2
import psycopg2.extras
import re
import json
from dotenv import load_dotenv
from together import Together
import time

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
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# --- Initialize Together AI Client ---
llm_client = Together(api_key=TOGETHER_API_KEY)

# --- CONFIGURATION & MAPPING ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
CHAPTER_ORDER_MAPPING = {
    "Chemistry": {
        11: ["Some Basic Concepts Of Chemistry.pdf", "Structure Of Atom.pdf", "Classification Of Elements And Periodicity.pdf", "Chemical Bonding And Molecular Structure.pdf", "Thermodynamics.pdf", "Equilibrium.pdf", "Redox Reactions.pdf", "Organic Chemistry Basics.pdf", "Hydrocarbons.pdf"],
        12: ["Solutions.pdf", "Electrochemistry.pdf", "Chemical Kinetics.pdf", "D And F Block.pdf", "Coordination Compounds.pdf", "Haloalkanes And Haloarenes.pdf", "Alcohol Phenols Ethers.pdf", "Aldehydes, Ketones And Carboxylic Acid.pdf", "Amines.pdf", "Biomolecules.pdf"]
    },
    "Maths": {
        11: ["Sets.pdf", "Relations And Functions.pdf", "Trigonometric Functions.pdf", "Complex Numbers And Quadratic Equations.pdf", "Linear Inequalities.pdf", "Permutations And Combinations.pdf", "Binomial Theorem.pdf", "Sequences And Series.pdf", "Straight Lines.pdf", "Conic Sections.pdf", "3D Geometry.pdf", "Limits And Derivatives.pdf", "Statistics.pdf", "Probability.pdf"],
        12: ["Relations And Functions.pdf", "Inverse Trigonometric Functions.pdf", "Matrices.pdf", "Determinants.pdf", "Contunuity And Differentiability.pdf", "Application Of Derivatives.pdf", "Integrals.pdf", "Application Of Integrals.pdf", "Differential Equations.pdf", "Vector Algebra.pdf", "3D Geometry.pdf", "Linear Programming.pdf", "Probability.pdf"]
    },
    "Physics": {
        11: ["Units And Measurements.pdf", "Motion In A Straight Line.pdf", "Motion In A Plane.pdf", "Laws Of Motion.pdf", "Work Energy Power.pdf", "System Of Particles And Rotational Motion.pdf", "Gravitation.pdf", "Mechanical Properties Of Solids.pdf", "Mechanical Properties Of Fluids.pdf", "Thermal Properties Of Matter.pdf", "Thermodynamics.pdf", "Kinetic Theory.pdf", "Oscillations.pdf", "Waves.pdf"],
        12: ["Electric Charges And Fields.pdf", "Electrostatic Potential And Capacitance.pdf", "Current Electricity.pdf", "Moving Charges And Magnetism.pdf", "Magnetism And Matter.pdf", "Electromagnetic Induction.pdf", "Alternating Current.pdf", "Electromagnetic Waves.pdf", "Ray Optics.pdf", "Wave Optics.pdf", "Dual Nature Of Radiation And Matter.pdf", "Atoms.pdf", "Nuclei.pdf", "SemiConductor Electronics.pdf"]
    }
}


def get_candidate_headings(doc):
    """Stage 1: A lenient function to extract any line that looks like a potential heading."""
    candidate_headings = []
    try:
        topic_pattern = re.compile(r"^\s*(\d+[\.\d+]*)\s+(.*)", re.MULTILINE)
        for page_num in range(min(5, doc.page_count)):
            page_text = doc[page_num].get_text()
            matches = topic_pattern.findall(page_text)
            for match in matches:
                full_line = f"{match[0]} {match[1].strip()}"
                candidate_headings.append(full_line)
        
        # --- DEBUG STATEMENT ---
        print(f"    - DEBUG: Stage 1 found {len(candidate_headings)} raw candidates.")
        for i, candidate in enumerate(candidate_headings):
            print(f"      - Candidate {i+1}: {candidate}")
            
        return candidate_headings
    except Exception as e:
        print(f"    - ❌ ERROR during candidate extraction: {e}")
        return []

def refine_topics_with_ai(headings, chapter_name):
    """Stage 2: Sends candidate headings to an LLM for final structuring and cleaning."""
    if not headings: return []
    headings_text = "\n".join(headings)
    
    # --- DEBUG STATEMENT ---
    print("    - DEBUG: Sending the following candidates to AI for refinement...")
    print(headings_text)
    
    try:
        system_message = (
            "You are a meticulous data extraction expert. Your task is to analyze the following list of candidate headings from a textbook. "
            "Your job is to identify only the official, numbered topics and sub-topics. "
            "Ignore any text that is not a real topic, like page headers, figure captions, or full sentences. "
            "Crucially, ignore the main chapter title itself, even if it is numbered."
            "Your entire response MUST be a single, valid JSON object with a single key 'topics'. "
            "The value for 'topics' must be a FLAT array of objects. Do NOT create nested structures like 'sub_topics'. "
            "Each object must have 'topic_number' and 'topic_name'. Preserve the original numbering exactly."
        )
        user_message_content = f"Please refine the following candidate headings for the chapter '{chapter_name}':\n\n--- CANDIDATE HEADINGS ---\n{headings_text}\n--- END OF HEADINGS ---"
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
        response = llm_client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages, max_tokens=3000, temperature=0.0, response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content.strip()
        
        # --- DEBUG STATEMENT ---
        print("    - DEBUG: AI returned the following raw JSON:")
        print(response_content)
        
        return json.loads(response_content).get('topics', [])
    except Exception as e:
        print(f"    - ❌ ERROR during AI refinement: {e}")
        return []

def get_full_text(doc):
    """Gets the full text content from a PDF document."""
    try:
        return "".join([page.get_text("text") + " " for page in doc]).strip()
    except Exception as e:
        print(f"    - ❌ ERROR extracting full text: {e}")
        return ""

def main():
    """PRODUCTION SCRIPT: Processes all files and populates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found.")
        return

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)

    try:
        with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT) as conn:
            print("✅ Successfully connected to the database.")
            with conn.cursor() as cur:
                for subject_name, classes in CHAPTER_ORDER_MAPPING.items():
                    for class_level, chapter_files in classes.items():
                        if not chapter_files: continue
                        print(f"\n===== Processing Subject: '{subject_name}' (Class {class_level}) =====")
                        
                        upsert_subject_query = "WITH ins AS (INSERT INTO subjects (name, class_level) VALUES (%s, %s) ON CONFLICT (name, class_level) DO NOTHING RETURNING id) SELECT id FROM ins UNION ALL SELECT id FROM subjects WHERE name = %s AND class_level = %s LIMIT 1;"
                        cur.execute(upsert_subject_query, (subject_name, class_level, subject_name, class_level))
                        subject_id = cur.fetchone()[0]

                        for chapter_number, filename in enumerate(chapter_files, 1):
                            chapter_name = os.path.splitext(filename)[0].strip()
                            
                            cur.execute("SELECT id FROM chapters WHERE subject_id = %s AND name = %s", (subject_id, chapter_name))
                            if cur.fetchone():
                                print(f"  -> Chapter {chapter_number}: '{chapter_name}' already exists. Skipping.")
                                continue

                            print(f"  -> Processing Chapter {chapter_number}: {chapter_name}")
                            pdf_path = os.path.join(pdf_root_full_path, subject_name, f"Class {class_level}", filename)
                            if not os.path.exists(pdf_path):
                                print(f"    - ❌ ERROR: File not found at {pdf_path}. Skipping.")
                                continue
                            
                            try:
                                doc = fitz.open(pdf_path)
                                full_chapter_text = get_full_text(doc)
                                
                                print("    - Stage 1: Extracting candidate headings...")
                                candidate_headings = get_candidate_headings(doc)
                                
                                print(f"    - Stage 2: Refining {len(candidate_headings)} candidates with AI...")
                                topics_data = refine_topics_with_ai(candidate_headings, chapter_name)
                                doc.close()

                                cur.execute(
                                    "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                    (subject_id, chapter_number, chapter_name, full_chapter_text),
                                )
                                chapter_id = cur.fetchone()[0]

                                if topics_data:
                                    # Final filter to remove the main chapter title from the topics list
                                    filtered_topics = [t for t in topics_data if chapter_name.lower() not in t.get('topic_name','').lower()]
                                    
                                    # --- DEBUG STATEMENT ---
                                    print(f"    - DEBUG: After filtering out chapter title, {len(filtered_topics)} topics remain to be inserted.")
                                    
                                    print(f"    - ✅ Success: Inserted {len(filtered_topics)} AI-refined topics.")
                                    topic_values = [(chapter_id, topic['topic_number'], topic['topic_name']) for topic in filtered_topics]
                                    if topic_values:
                                        psycopg2.extras.execute_values(cur, "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s", topic_values)
                                else:
                                    print(f"    - ⚠️ Warning: No topics found for {chapter_name} after AI refinement.")
                            except Exception as e:
                                print(f"  ❌ CRITICAL ERROR processing file {filename}: {e}")
                                        
            print("\n✅ All data has been successfully inserted and committed.")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
