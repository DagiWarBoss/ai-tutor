import os
import re

OCR_TEXT_PATH = r"ocr_cache\Chemical Bonding And Molecular Structure.txt"

def extract_questions(file_path, subject="science"):
    """
    subject = 'science' (Physics/Chemistry) or 'math'
    Extract questions based on section headers and numbering.
    """
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Subject-based regex
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


def main():
    if not os.path.exists(OCR_TEXT_PATH):
        print("OCR text file not found. Please re-run the OCR process first.")
        return

    # Example usage
    # Change subject to 'math' for mathematics books
    questions = extract_questions(OCR_TEXT_PATH, subject="science")

    print(f"\nExtracted {len(questions)} questions:\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")


if __name__ == "__main__":
    main()
