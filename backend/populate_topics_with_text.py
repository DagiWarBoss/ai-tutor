import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os
import csv
import json

# ======= Update these paths for YOUR system =======
pdf_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise\Chemistry\Class 11\Some Basic Concepts Of Chemistry.pdf"
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ocr_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"
topic_csv_path = "topics_output.csv"
question_csv_path = "questions_output.csv"
# ================================================

pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_ocr_text(pdf_path, poppler_path, dpi=300):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    print(f"Converting PDF pages to images ...")
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    print(f"Found {len(images)} pages ... Running OCR ...")
    all_text = []
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        text = text.replace('-\n', '')  # Clean up broken words
        all_text.append(text)
    print("OCR extraction complete.")
    return "\n".join(all_text)

def extract_topics(chapter_text):
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

def extract_questions(chapter_text):
    # Find the "EXERCISES" section (case-insensitive, 20 chars of context before)
    exercises_pat = re.compile(r'EXERCISES(.+)', re.DOTALL | re.IGNORECASE)
    ex_match = exercises_pat.search(chapter_text)
    if not ex_match:
        print('No EXERCISES section found!')
        return []
    exercises_text = ex_match.group(1)
    # Now extract questions, e.g.: "1.1", "1.2", or "1.25" formats.
    question_pat = re.compile(r'(\d+\.\d+|\d+\.)\s*-\s*(.+?)(?=\n\d+\.\d+|\n\d+\.|\n\n|$)', re.DOTALL)
    raw_questions = question_pat.findall(exercises_text)
    questions = []
    for qnum, qtext in raw_questions:
        questions.append({'question_number': qnum.strip('.'), 'question_text': qtext.strip()})
    return questions

def save_csv(data, fields, csv_path):
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print(f"Saved data to {csv_path}")

if __name__ == "__main__":
    # Step 1: OCR conversion
    ocr_text = pdf_to_ocr_text(pdf_path, poppler_path, dpi=300)
    with open(ocr_txt_path, "w", encoding="utf-8") as f:
        f.write(ocr_text)
    print(f"OCR text written to {ocr_txt_path}")

    # Step 2: Topic extraction by numbered headings
    topics = extract_topics(ocr_text)
    print(f"\nExtracted {len(topics)} topics.")
    # Save topics to CSV (customize fields if you want more metadata)
    save_csv(topics, ['topic_number', 'title', 'content'], topic_csv_path)

    # Step 3: Question extraction from EXERCISES section
    questions = extract_questions(ocr_text)
    print(f"Extracted {len(questions)} questions.")
    save_csv(questions, ['question_number', 'question_text'], question_csv_path)

    # Quick preview of both
    print('\nSample topics:')
    for topic in topics[:5]:
        print(f"{topic['topic_number']} - {topic['title']}\n{topic['content'][:150]}...\n")

    print('\nSample questions:')
    for question in questions[:5]:
        print(f"Q{question['question_number']}: {question['question_text'][:120]}...\n")
