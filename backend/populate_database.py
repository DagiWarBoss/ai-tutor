import os
import psycopg2
import re
from dotenv import load_dotenv
from llama_index.core.node_parser import HierarchicalNodeParser
from llama_index.core.node_parser import get_leaf_nodes
from llama_index.readers.file import PDFReader

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- CONFIGURATION ---
PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"

def extract_structured_data_debug(pdf_path):
    """A debug version to inspect the metadata from the layout parser."""
    try:
        print(f"    - DEBUG: Loading PDF with layout parser: {os.path.basename(pdf_path)}")
        reader = PDFReader()
        documents = reader.load_data(file=pdf_path)
        
        print("    - DEBUG: Parsing nodes to find hierarchy...")
        node_parser = HierarchicalNodeParser.from_defaults()
        nodes = node_parser.get_nodes_from_documents(documents)
        leaf_nodes = get_leaf_nodes(nodes)

        print("\n    --- METADATA INSPECTION ---")
        print("    - The following lines show the metadata for each text block found.")
        print("    - Look for keys like 'Header', 'heading', 'title', or font information.\n")

        for i, node in enumerate(leaf_nodes):
            # This is the key debug line. It prints all the info the parser found.
            print(f"    - [Node {i+1}] Metadata: {node.metadata}")
            # Also print a snippet of the text for context
            text_snippet = node.get_content()[:80].replace('\n', ' ')
            print(f"      - Text Snippet: \"{text_snippet}...\"")


        # We will return empty for now as we are only debugging
        return "", []

    except Exception as e:
        print(f"    - ❌ ERROR during layout-aware parsing of {os.path.basename(pdf_path)}: {e}")
        return "", []


def main():
    """Runs the debug script on a single file."""
    print("--- Starting DEBUG script for Layout-Aware Parser ---")
    
    # --- Define the single file we want to test ---
    subject_name = "Chemistry"
    class_level = 11
    # You can change this to any PDF you want to inspect
    filename_to_test = "Some Basic Concepts Of Chemistry.pdf" 

    pdf_path = os.path.join(script_dir, PDF_ROOT_FOLDER, subject_name, f"Class {class_level}", filename_to_test)

    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: Test file not found at {pdf_path}. Please check the path and filename.")
        return

    print(f"Processing single file for debugging: {filename_to_test}")
    extract_structured_data_debug(pdf_path)
    
    print("\n--- DEBUG script finished ---")
    print("Please copy the full output from the 'METADATA INSPECTION' section and share it.")


if __name__ == '__main__':
    main()
