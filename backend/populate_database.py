import os
from dotenv import load_dotenv
from heading_extractor import HeadingExtractor

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

PDF_ROOT_FOLDER = "NCERT_PCM_ChapterWise"
TARGET_CHAPTER = "Chemical Bonding And Molecular Structure.pdf"
CHAPTER_NUMBER = "4"  # Change per chapter

def main():
    """Extract headings from a specific chapter using the HeadingExtractor utility."""
    extractor = HeadingExtractor(PDF_ROOT_FOLDER)
    
    # Extract headings from the target chapter
    subject = "Chemistry"
    class_name = "Class 11"
    
    headings = extractor.extract_all_chapter_headings(subject, class_name, TARGET_CHAPTER, CHAPTER_NUMBER)
    
    print(f"\nMatched clean candidate headings for '{TARGET_CHAPTER}':")
    for num, text in headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(headings)}")

if __name__ == '__main__':
    main()
