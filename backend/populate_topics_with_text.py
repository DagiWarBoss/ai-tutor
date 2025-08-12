import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os

# ----- Paths/Config -----
pdf_path = r"..."   # your chapter PDF
poppler_path = r"..."  # your Poppler bin
tesseract_path = r"..."  # Tesseract exe
chapter_id = ...        # map from your chapters table
class_number = ...      # e.g., "11"
subject = ...           # e.g., "Chemistry"
ocr_txt_path = "chapter_ocr.txt"

pytesseract.pytesseract.tesseract_cmd = tesseract_path

def pdf_to_ocr_text(pdf_path, poppler_path, dpi=300):
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    ocr_text = "\n".join([pytesseract.image_to_string(img).replace('-\n','') for img in images])
    return ocr_text

def extract_topics(chapter_text):
    topic_pat = re.compile(r'^(\d+(?:\.\d+)+)\s+([^\n]+)', re.MULTILINE)
    matches = list(topic_pat.finditer(chapter_text))
    topics = []
    for i, m in enumerate(matches):
        start, end = m.end(), matches[i+1].start() if i+1 < len(matches) else len(chapter_text)
        topics.append({
            'topic_number': m.group(1),
            'title': m.group(2).strip(),
            'content': chapter_text[start:end].strip()
        })
    return topics

def extract_questions(chapter_text):
    # Find "EXERCISES" section
    exercises_pat = re.compile(r'EXERCISES(.*)', re.DOTALL)
    ex_match = exercises_pat.search(chapter_text)
    if not ex_match:
        print('No EXERCISES section found!')
        return []
    exercises_text = ex_match.group(1)
    # Find numbered questions, e.g., "1.1", "1.2", ... or sometimes just "1."
    question_pat = re.compile(r'(\d+\.\d+|\d+\.)\s*-\s*(.+?)(?=\n\d+\.\d+|\n\d+\.|\n\n|$)', re.DOTALL)
    questions = []
    for qm in question_pat.finditer(exercises_text):
        qnum = qm.group(1)
        qtext = qm.group(2).strip()
        questions.append({'question_number': qnum, 'question_text': qtext})
    return questions

# --- MAIN ---
if __name__ == "__main__":
    # Step 1: OCR
    ocr_text = pdf_to_ocr_text(pdf_path, poppler_path, dpi=300)
    with open(ocr_txt_path, "w", encoding="utf-8") as f:
        f.write(ocr_text)

    # Step 2: Topic extraction
    topics = extract_topics(ocr_text)
    print(f"Extracted {len(topics)} topics.")

    # Step 3: Question extraction
    questions = extract_questions(ocr_text)
    print(f"Extracted {len(questions)} questions.")

    # Step 4: DB upload (example, pseudo-code)
    # import supabase
    # sb = supabase.Client(...)
    # for topic in topics:
    #     sb.table('topics').insert({
    #         'chapter_id': chapter_id,
    #         'class_number': class_number,
    #         'subject': subject,
    #         'topic_number': topic['topic_number'],
    #         'name': topic['title'],
    #         'full_text': topic['content']
    #     }).execute()

    # for question in questions:
    #     sb.table('questions').insert({
    #         'chapter_id': chapter_id,
    #         'class_number': class_number,
    #         'subject': subject,
    #         'question_number': question['question_number'],
    #         'question_text': question['question_text']
    #     }).execute()

    # Alternatively: save to CSV/JSON for manual import

    # For now, just preview
    for topic in topics[:5]:
        print(f"Topic {topic['topic_number']}: {topic['title']}\n")
    for question in questions[:5]:
        print(f"Q{question['question_number']}: {question['question_text']}\n")
