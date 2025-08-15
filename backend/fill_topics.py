import re
import logging
import pandas as pd

log = logging.getLogger(__name__)

def normalize(text):
    """
    Normalize text by removing non-alphanumeric characters and lowercasing.
    This helps in better matching of extracted text and headings.
    """
    return re.sub(r'\W+', '', text).lower()

def extract_all_topics_with_split(full_text, topic_df):
    """
    Extract topics from full_text based on heading positions derived from topic_df.
    The function normalizes and searches headings in the full_text to find positions.
    It then slices the full_text to get content between consecutive headings.
    
    Parameters:
    - full_text: str, entire text extracted from a PDF.
    - topic_df: pandas DataFrame with columns including 'heading_number' and 'heading_text'.

    Returns:
    - List of dictionaries with keys 'heading_number', 'heading_text', and 'content'.
    """
    topics = []
    norm_full_text = normalize(full_text)
    topic_df = topic_df.sort_values('heading_number')
    headings = topic_df['heading_text'].tolist()
    heading_numbers = topic_df['heading_number'].tolist()

    positions = []
    for idx, heading in enumerate(headings):
        norm_heading = normalize(heading)
        pos = norm_full_text.find(norm_heading)

        if pos == -1:
            # Attempt searching using combined heading number + heading text
            combined = normalize(f"{heading_numbers[idx]} {heading}")
            pos = norm_full_text.find(combined)

            if pos == -1:
                log.warning(f"Heading not found in PDF text: '{heading[:30]}...'")

        positions.append(pos)

    # Filter out headings not found (pos == -1) for slicing
    found_positions = [(pos, heading, heading_numbers[i]) for i, pos in enumerate(positions) if pos != -1]

    if not found_positions:
        log.info("No headings matched in text.")
        return []

    # Sort found headings by position
    found_positions.sort(key=lambda x: x[0])

    # Extract text between consecutive headings to form topics
    for i in range(len(found_positions)):
        start_pos = found_positions[i][0]
        heading = found_positions[i][1]
        heading_no = found_positions[i][2]

        if i + 1 < len(found_positions):
            end_pos = found_positions[i+1][0]
        else:
            end_pos = len(norm_full_text)

        # Locate corresponding positions in original full_text (case insensitive)
        start_index = full_text.lower().find(heading.lower())
        if i + 1 < len(found_positions):
            next_heading = found_positions[i+1][1]
            end_index = full_text.lower().find(next_heading.lower())
        else:
            end_index = len(full_text)

        if start_index == -1:
            # Fallback to approximate slicing from normalized positions
            start_index = start_pos
        if end_index == -1 or end_index <= start_index:
            end_index = len(full_text)

        topic_text = full_text[start_index:end_index].strip()
        topics.append({
            'heading_number': heading_no,
            'heading_text': heading,
            'content': topic_text
        })

    return topics

# Example usage:
if __name__ == "__main__":
    import sys

    # Configure logging to print warnings and above
    logging.basicConfig(level=logging.WARNING)

    # Load topics dataframe from CSV file
    csv_file = "final_verified_topics.csv"
    try:
        topic_df = pd.read_csv(csv_file)
    except Exception as e:
        log.error(f"Failed to load topics CSV file '{csv_file}': {e}")
        sys.exit(1)

    # Load full text from a PDF extraction process (placeholder)
    # This should be replaced with actual text extraction from the PDF file.
    pdf_file = "Chemical Bonding And Molecular Structure.pdf"
    try:
        # For demonstration, read the whole PDF text from a txt file or extract here
        with open(pdf_file.replace('.pdf', '.txt'), 'r', encoding='utf-8') as f:
            full_text = f.read()
    except Exception as e:
        log.error(f"Failed to load full text from '{pdf_file}': {e}")
        sys.exit(1)

    # Filter topics for the selected PDF file / chapter (optional)
    chapter_topics = topic_df[topic_df['chapter_file'] == pdf_file]

    # Extract topics from full text
    extracted_topics = extract_all_topics_with_split(full_text, chapter_topics)

    # Print or save extracted topics
    for topic in extracted_topics:
        print(f"Heading {topic['heading_number']}: {topic['heading_text']}")
        print(f"Content snippet: {topic['content'][:500]}...\n{'-'*80}\n")

    # Optionally save extracted topics to a file
    # pd.DataFrame(extracted_topics).to_csv("extracted_topics.csv", index=False)
