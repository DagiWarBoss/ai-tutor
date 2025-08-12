import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os

# CHANGE THESE AS NEEDED
pdf_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\Some-Basic-Concepts-Of-Chemistry.pdf"
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Optional: Output TXT and topics CSV/JSON file
txt_output_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"

pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_text(pdf_path, poppler_path, dpi=300):
    print("Converting PDF pages to images...")
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    print(f"Found {len(images)} pages. Running OCR...")
    ocr_text = \n".join([pytesseract.image_to_string(image) for image in images])
    print(f"OCR extraction complete.")
    return ocr_text

def extract_ncert_topics(chapter_text):
    heading_re = re.compile(r'^(\d+(?:\.\d+)+)\s+([^\n]+)', re.MULTILINE)
    matches = list(heading_re.finditer(chapter_text))
    topics = []
    for i, match in enumerate(matches):
        topic_num = match.group(1)
        topic_title = match.group(2).strip()
        start = match.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(chapter_text)
        content = chapter_text[start:end].strip()
        topics.append({
            'topic_number': topic_num,
            'title': topic_title,
            'content': content
        })
    return topics

if __name__ == "__main__":
    # Step 1: OCR the PDF
    ocr_text = pdf_to_text(pdf_path, poppler_path, dpi=300)
    with open(txt_output_path, "w", encoding="utf-8") as f:
        f.write(ocr_text)
    print(f"OCR text written to {txt_output_path}")

    # Step 2: Extract topics by numbered headings
    topics = extract_ncert_topics(ocr_text)
    print(f"\nExtracted {len(topics)} topics.\n")
    for topic in topics:
        print(f"{topic['topic_number']} - {topic['title']}\n{'-'*60}")
        print(topic['content'][:300], "\n---\n")

    # You can optionally save as CSV, JSON, or insert into database here
