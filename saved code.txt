import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os

# ========== PATHS: UPDATE AS NEEDED ==========
pdf_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Some Basic Concepts Of Chemistry.pdf"
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ocr_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"
# ==============================================

pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_ocr_text(pdf_path, poppler_path, dpi=300):
    # Extra check for path
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    print("Converting PDF pages to images ...")
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    print(f"Found {len(images)} pages ... Running OCR ...")
    all_text = []
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        # Remove hyphen at line breaks (common in OCR)
        text = text.replace('-\n', '')
        all_text.append(text)
    print("OCR extraction complete.")
    return "\n".join(all_text)

def extract_ncert_topics(chapter_text):
    # Robust regex: matches lines like "1.3 Physical property", "1.7.2 Atomic Mass"
    heading_re = re.compile(r'^(\d+(?:\.\d+)+)\s+([^\n]+)', re.MULTILINE)
    matches = list(heading_re.finditer(chapter_text))
    topics = []
    for i, match in enumerate(matches):
        topic_num = match.group(1)
        topic_title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(chapter_text)
        content = chapter_text[start:end].strip()
        topics.append({'topic_number': topic_num, 'title': topic_title, 'content': content})
    return topics

if __name__ == "__main__":
    # STEP 1: OCR conversion
    ocr_text = pdf_to_ocr_text(pdf_path, poppler_path, dpi=300)
    with open(ocr_txt_path, "w", encoding="utf-8") as f:
        f.write(ocr_text)
    print(f"OCR text written to {ocr_txt_path}")

    # STEP 2: Topic extraction by numbered headings
    topics = extract_ncert_topics(ocr_text)
    print(f"\nExtracted {len(topics)} topics:\n")
    for topic in topics:
        print(f"{topic['topic_number']} - {topic['title']}\n{'-'*60}")
        print(topic['content'][:250], "\n---\n")

    # You can process 'topics' into your database, CSV, JSON, etc.
