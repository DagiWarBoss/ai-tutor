import os
import psycopg2
import psycopg2.extras
import re
from dotenv import load_dotenv
from llama_index.core.node_parser import HierarchicalNodeParser
from llama_index.core.node_parser import get_leaf_nodes
from llama_index.readers.file import PDFReader

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

# =================================================================
# FINALIZED CHAPTER ORDER MAPPING (Based on your exact filenames)
# =================================================================
CHAPTER_ORDER_MAPPING = {
    "Chemistry": {
        11: [
            "Some Basic Concepts Of Chemistry.pdf", "Structure Of Atom.pdf",
            "Classification Of Elements And Periodicity.pdf", "Chemical Bonding And Molecular Structure.pdf",
            "Thermodynamics.pdf", "Equilibrium.pdf", "Redox Reactions.pdf",
            "Organic Chemistry Basics.pdf", "Hydrocarbons.pdf"
        ],
        12: [
            "Solutions.pdf", "Electrochemistry.pdf", "Chemical Kinetics.pdf", "D And F Block.pdf",
            "Coordination Compounds.pdf", "Haloalkanes And Haloarenes.pdf", "Alcohol Phenols Ethers.pdf",
            "Aldehydes, Ketones And Carboxylic Acid.pdf", "Amines.pdf", "Biomolecules.pdf"
        ]
    },
    "Maths": {
        11: [
            "Sets.pdf", "Relations And Functions.pdf", "Trigonometric Functions.pdf",
            "Complex Numbers And Quadratic Equations.pdf", "Linear Inequalities.pdf",
            "Permutations And Combinations.pdf", "Binomial Theorem.pdf", "Sequences And Series.pdf",
            "Straight Lines.pdf", "Conic Sections.pdf", "3D Geometry.pdf",
            "Limits And Derivatives.pdf", "Statistics.pdf", "Probability.pdf"
        ],
        12: [
            "Relations And Functions.pdf", "Inverse Trigonometric Functions.pdf", "Matrices.pdf",
            "Determinants.pdf", "Contunuity And Differentiability.pdf",
            "Application Of Derivatives.pdf", "Integrals.pdf", "Application Of Integrals.pdf",
            "Differential Equations.pdf", "Vector Algebra.pdf", "3D Geometry.pdf",
            "Linear Programming.pdf", "Probability.pdf"
        ]
    },
    "Physics": {
        11: [
            "Units And Measurements.pdf", "Motion In A Straight Line.pdf", "Motion In A Plane.pdf",
            "Laws Of Motion.pdf", "Work Energy Power.pdf", "System Of Particles And Rotational Motion.pdf",
            "Gravitation.pdf", "Mechanical Properties Of Solids.pdf", "Mechanical Properties Of Fluids.pdf",
            "Thermal Properties Of Matter.pdf", "Thermodynamics.pdf", "Kinetic Theory.pdf",
            "Oscillations.pdf", "Waves.pdf"
        ],
        12: [
            "Electric Charges And Fields.pdf", "Electrostatic Potential And Capacitance.pdf",
            "Current Electricity.pdf", "Moving Charges And Magnetism.pdf", "Magnetism And Matter.pdf",
            "Electromagnetic Induction.pdf", "Alternating Current.pdf", "Electromagnetic Waves.pdf",
            "Ray Optics.pdf", "Wave Optics.pdf", "Dual Nature Of Radiation And Matter.pdf",
            "Atoms.pdf", "Nuclei.pdf", "SemiConductor Electronics.pdf"
        ]
    }
}

def extract_structured_data(pdf_path):
    """Uses a layout-aware parser to extract text and hierarchical topics."""
    try:
        # Use the PDFReader with layout parsing enabled
        reader = PDFReader()
        documents = reader.load_data(file=pdf_path)
        
        # The full text is simply the content of the loaded documents
        full_text = "\n".join([doc.get_content() for doc in documents])

        # Use the HierarchicalNodeParser to find headings
        node_parser = HierarchicalNodeParser.from_defaults()
        nodes = node_parser.get_nodes_from_documents(documents)
        leaf_nodes = get_leaf_nodes(nodes)

        topics = []
        topic_pattern = re.compile(r"^\s*(\d+[\.\d+]*)\s+(.*)")

        for node in leaf_nodes:
            # We look for headings in the node metadata, which is where the parser puts them
            if 'Header' in node.metadata:
                header_text = node.metadata['Header']
                match = topic_pattern.match(header_text)
                if match:
                    topic_number = match.group(1)
                    topic_name = match.group(2).strip()
                    topics.append({"topic_number": topic_number, "topic_name": topic_name})

        return full_text, topics

    except Exception as e:
        print(f"    - ❌ ERROR during layout-aware parsing of {os.path.basename(pdf_path)}: {e}")
        return "", []


def main():
    """Walks through the folder structure, uses layout-aware parsing, and populates the database."""
    if not all([DB_HOST, DB_PASSWORD, DB_USER, DB_PORT, DB_NAME]):
        print("❌ Error: Database credentials not found. Ensure .env file is correct.")
        return

    pdf_root_full_path = os.path.join(script_dir, PDF_ROOT_FOLDER)

    try:
        with psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        ) as conn:
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
                            
                            full_chapter_text, topics_data = extract_structured_data(pdf_path)

                            if not full_chapter_text:
                                print(f"    - ❌ ERROR: Could not extract any text from {filename}. Skipping.")
                                continue

                            cur.execute(
                                "INSERT INTO chapters (subject_id, chapter_number, name, full_text) VALUES (%s, %s, %s, %s) RETURNING id",
                                (subject_id, chapter_number, chapter_name, full_chapter_text),
                            )
                            chapter_id = cur.fetchone()[0]

                            if topics_data:
                                print(f"    - Found {len(topics_data)} topics using layout parser. Inserting...")
                                topic_values = [(chapter_id, topic['topic_number'], topic['topic_name']) for topic in topics_data]
                                psycopg2.extras.execute_values(cur, "INSERT INTO topics (chapter_id, topic_number, name) VALUES %s", topic_values)
                            else:
                                print(f"    - Warning: No topics found for {chapter_name} using layout parser.")
                                        
            print("\n✅ All data has been successfully inserted and committed.")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
    finally:
        print("\nScript finished.")

if __name__ == '__main__':
    main()
