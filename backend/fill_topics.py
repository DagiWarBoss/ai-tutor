import os
import pandas as pd
import fitz  # PyMuPDF
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pdf_extract")

PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\origins"
OCR_CACHE_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\ocr_cache"

# Chapter configurations: subject, class, pdf filename, chapter number
CHAPTER_CONFIG = {
    12: {
        "subject": "Chemistry",
        "class": "Class 11",
        "pdf_filename": "Aldehydes Ketones And Carboxylic Acid.pdf",
        "chapter_num": 8,
    },
    # add other chapters as needed here...
}

def pdf_to_text(pdf_path, cache_folder):
    """Extract text from PDF file, using cache if available, else extract and save."""
    fname = os.path.basename(pdf_path)
    cache_file = os.path.join(cache_folder, fname.replace('.pdf', '.txt').replace(' ', '_'))
    if os.path.exists(cache_file):
        log.info(f"Using cached OCR text: {cache_file}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            text = f.read()
        return text

    log.info(f"Extracting text from PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    with open(cache_file, 'w', encoding='utf-8') as f:
        f.write(full_text)
    log.info(f"Saved OCR text to cache: {cache_file}")
    return full_text

def extract_all_topics_with_split(full_text, topic_df):
    """
    Extract text segments from full_text based on the headings in topic_df.
    Return a list of dicts with heading info and extracted content.
    """
    topics = []
    headings = topic_df.sort_values('heading_number')['heading_text'].tolist()

    # Find indices (positions) of each heading in the text
    positions = []
    for heading in headings:
        pos = full_text.find(heading)
        if pos == -1:
            log.warning(f"Heading not found in PDF text: {heading[:30]}...")
        positions.append(pos)

    # Pair each heading with its start index
    headings_positions = list(zip(headings, positions))

    # Filter out headings not found in text (pos == -1)
    headings_positions = [hp for hp in headings_positions if hp[1] >= 0]

    # Sort based on position
    headings_positions.sort(key=lambda x: x[1])

    # Extract topic texts between headings
    for i, (heading, pos) in enumerate(headings_positions):
        start = pos
        if i + 1 < len(headings_positions):
            end = headings_positions[i + 1][1]
        else:
            end = len(full_text)
        content = full_text[start:end].strip()
        topics.append({"heading": heading, "content": content})
        log.info(f"Extracted topic '{heading}' text length: {len(content)}")
    return topics

def main():
    # Load master CSV file containing headings and related chapter info
    master_csv_path = "final_verified_topics.csv"
    df_topics = pd.read_csv(master_csv_path)

    for chap_id, config in CHAPTER_CONFIG.items():
        subj = config["subject"]
        cls = config["class"]
        pdf_filename = config["pdf_filename"]

        pdf_path = os.path.join(PDF_ROOT_FOLDER, subj, cls, pdf_filename)
        log.info(f"\nProcessing PDF: {pdf_path}")

        # Special case: Use OCR cache text file directly for Aldehydes Ketones And Carboxylic Acid.pdf
        if pdf_filename == "Aldehydes Ketones And Carboxylic Acid.pdf":
            cache_path = os.path.join(OCR_CACHE_FOLDER, "Aldehydes_Ketones_Carboxylic_12.txt")
            if not os.path.exists(cache_path):
                log.error(f"Cache file not found: {cache_path}. Cannot proceed.")
                continue
            with open(cache_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
            log.info(f"Loaded cached OCR text from {cache_path}")
        else:
            if not os.path.exists(pdf_path):
                log.error(f"PDF file not found at {pdf_path}. Skipping.")
                continue
            full_text = pdf_to_text(pdf_path, OCR_CACHE_FOLDER)

        # Filter master CSV for entries related to current PDF
        chapter_topics_df = df_topics[df_topics["chapter_file"] == pdf_filename]
        if chapter_topics_df.empty:
            log.warning(f"No topics found for PDF: {pdf_filename}")
            continue

        # Extract topics with their text content
        extracted_topics = extract_all_topics_with_split(full_text, chapter_topics_df)

        # Example action: print summary of extracted topics lengths
        log.info(f"Extracted {len(extracted_topics)} topics from {pdf_filename}")
        for topic in extracted_topics:
            log.info(f"Topic: {topic['heading']}, Content length: {len(topic['content'])}")

        # Here you can do additional processing like saving to DB or files if needed

if __name__ == "__main__":
    main()
