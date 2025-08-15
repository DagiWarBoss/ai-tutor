import os
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

# ==== STEP 1: OCR extraction ====
def pdf_to_text(pdf_path, txt_path):
    doc = fitz.open(pdf_path)
    full_text = []
    print("Starting OCR extraction from PDF...")
    for page_num, page in enumerate(doc, 1):
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        text = pytesseract.image_to_string(img)
        full_text.append(text)
        print(f"OCR page {page_num}/{len(doc)} done")
    os.makedirs(os.path.dirname(txt_path), exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))
    print(f"OCR extraction complete: {txt_path}\n")


# ==== STEP 2: Question Extraction ====
def extract_questions(file_path, subject="science"):
    """
    subject = 'science' (Physics/Chemistry) or 'math'
    Extract questions based on section headers and numbering.
    """
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Subject-specific section headers
    if subject.lower() == "math":
        header_pattern = re.compile(r"\b(EXAMPLES?|ILLUSTRATIONS?|PRACTICE QUESTIONS?|EXERCISES?)\b", re.IGNORECASE)
    else:  # Physics/Chemistry
        header_pattern = re.compile(r"\b(EXERCISES?|PROBLEMS|QUESTION BANK)\b", re.IGNORECASE)

    all_caps_heading = re.compile(r"^[A-Z0-9 '\-]{5,}$")
    question_number_pattern = re.compile(r"^(\d+[\.\)]|•)\s+")

    in_section = False
    current_question = []

    for line in lines:
        line_strip = line.strip()

        # --- Detect start of target section ---
        if not in_section and header_pattern.search(line_strip):
            in_section = True
            continue

        # --- Detect section end ---
        if in_section and all_caps_heading.match(line_strip) and not question_number_pattern.match(line_strip):
            if current_question:
                questions.append(" ".join(current_question).strip())
                current_question = []
            break

        if in_section:
            if question_number_pattern.match(line_strip):
                # Save previous question
                if current_question:
                    questions.append(" ".join(current_question).strip())
                    current_question = []
                current_question.append(line_strip)
            else:
                # Continuation of current question
                if current_question:
                    current_question.append(line_strip)

    # Save any remaining question
    if current_question:
        questions.append(" ".join(current_question).strip())

    return questions


# ==== MAIN WORKFLOW ====
def main():
    # ----------- USER INPUTS (modify as needed) -----------
    # Path to source PDF
    PDF_PATH = r"books\Chemical Bonding And Molecular Structure.pdf"
    # Path to cache text file
    OCR_TXT_PATH = r"ocr_cache\Chemical Bonding And Molecular Structure.txt"
    # Choose 'science' for Chemistry/Physics or 'math' for Maths
    SUBJECT = "science"
    # ------------------------------------------------------

    # If OCR cache not present, run OCR
    if not os.path.exists(OCR_TXT_PATH):
        pdf_to_text(PDF_PATH, OCR_TXT_PATH)
    else:
        print(f"OCR cache found: {OCR_TXT_PATH}")

    # Extract questions
    questions = extract_questions(OCR_TXT_PATH, subject=SUBJECT)
    print(f"\nExtracted {len(questions)} questions:\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")


if __name__ == "__main__":
    main()
