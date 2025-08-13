import re
import pandas as pd

def clean_ocr_text(text: str) -> str:
    # Simplified: Focus on basics to avoid over-correction
    text = re.sub(r'[^\S\r\n]+', ' ', text)  # Replace multiple spaces/tabs with single space
    text = re.sub(r'\s*\n\s*', '\n', text)   # Normalize newlines
    return text.strip()

def extract_topics_and_questions(ocr_text: str, topics_from_csv: pd.DataFrame):
    # Clean the OCR text first
    ocr_text = clean_ocr_text(ocr_text)
    
    extracted_topics = []
    
    # Refined regex: Flexible for sublevels, requires space or end after number to avoid over-matching
    topic_numbers_escaped = [re.escape(str(num)).replace('\\.', r'(?:\.|\s|\-)?') for num in topics_from_csv['heading_number']]
    heading_pattern = re.compile(r'(?m)^\s*(' + '|'.join(topic_numbers_escaped) + r')(?:\s|\.|$)', re.IGNORECASE)
    matches = list(heading_pattern.finditer(ocr_text))
    topic_locations = {}
    text_length = len(ocr_text)
    for match in matches:
        # Normalize matched number (remove spaces, fix dashes)
        cleaned_num = re.sub(r'\s+', '', match.group(1)).replace('-', '.')
        pos = match.start()
        # Filter: Ignore matches in likely exercise sections (last 20% of text)
        if pos < text_length * 0.8:
            if cleaned_num not in topic_locations:  # Avoid duplicates
                topic_locations[cleaned_num] = pos
                print(f"    - Matched heading: {cleaned_num} at position {pos}")  # Log for debugging
    
    # Log expected vs found
    expected_topics = set(topics_from_csv['heading_number'].astype(str))
    found_topics = set(topic_locations.keys())
    missing_topics = expected_topics - found_topics
    print(f"    - Found {len(topic_locations)} of {len(topics_from_csv)} topic headings in the PDF text.")
    if missing_topics:
        print(f"    - Missing topics: {', '.join(sorted(missing_topics))} (check OCR for artifacts or adjust regex).")
        for miss in list(missing_topics)[:3]:  # Limit to 3 for brevity
            miss_pos = ocr_text.find(miss)
            if miss_pos != -1:
                snippet = ocr_text[max(0, miss_pos-50):miss_pos+50].replace('\n', ' ')
                print(f"      - Snippet around missing '{miss}': ...{snippet}...")

    # Extract content for found topics
    sorted_locations = sorted(topic_locations.items(), key=lambda x: x[1])
    for i, (topic_num, start_pos) in enumerate(sorted_locations):
        end_pos = sorted_locations[i+1][1] if i+1 < len(sorted_locations) else len(ocr_text)
        content = ocr_text[start_pos:end_pos].strip()
        title = topics_from_csv[topics_from_csv['heading_number'] == topic_num]['heading_text'].values[0] if not topics_from_csv[topics_from_csv['heading_number'] == topic_num].empty else ''
        extracted_topics.append({'topic_number': topic_num, 'title': title, 'content': content})
    
    # Improved fallback: Scan for missing subtopics within each extracted topic's content
    for topic in extracted_topics[:]:  # Copy to avoid modification issues
        content = topic['content']
        sub_matches = heading_pattern.finditer(content)
        for sub_match in sub_matches:
            sub_cleaned = re.sub(r'\s+', '', sub_match.group(1)).replace('-', '.')
            if sub_cleaned in missing_topics and sub_cleaned not in topic_locations:
                sub_start = sub_match.start() + topic_locations[topic['topic_number']]
                topic_locations[sub_cleaned] = sub_start
                sub_end = len(ocr_text)  # Default to end; adjust if next found
                for next_num, next_pos in sorted_locations:
                    if next_pos > sub_start:
                        sub_end = next_pos
                        break
                sub_content = ocr_text[sub_start:sub_end].strip()
                sub_title = topics_from_csv[topics_from_csv['heading_number'] == sub_cleaned]['heading_text'].values[0] if not topics_from_csv[topics_from_csv['heading_number'] == sub_cleaned].empty else ''
                extracted_topics.append({'topic_number': sub_cleaned, 'title': sub_title, 'content': sub_content})
                print(f"    - Fallback match for subtopic: {sub_cleaned} at position {sub_start}")
                missing_topics.remove(sub_cleaned)  # Update missing set

    return extracted_topics  # Only return topics
