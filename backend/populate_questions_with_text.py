import os
import re

# Path to OCR text file
OCR_TEXT_PATH = r"ocr_cache\Chemical Bonding And Molecular Structure.txt"

def extract_all_questions(file_path):
    """
    Extract all questions in the book.
    - A question is any text ending with '?'
    - Can span multiple lines until another question starts or a blank line appears
    """
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_question = []
    question_pattern = re.compile(r".*\?$")  # line ending in '?'

    for line in lines:
        line_strip = line.strip()

        # skip empty lines unless in middle of question
        if not line_strip:
            if current_question:
                questions.append(" ".join(current_question).strip())
                current_question = []
            continue

        if question_pattern.match(line_strip):
            # This line ends with a question mark
            if current_question:
                current_question.append(line_strip)
                questions.append(" ".join(current_question).strip())
                current_question = []
            else:
                questions.append(line_strip)
        else:
            # Maybe it's the continuation of a multi-line question
            if current_question:
                current_question.append(line_strip)

    # Save if something left
    if current_question:
        questions.append(" ".join(current_question).strip())

    return questions


def main():
    if not os.path.exists(OCR_TEXT_PATH):
        print(f"OCR text file not found: {OCR_TEXT_PATH}")
        return

    questions = extract_all_questions(OCR_TEXT_PATH)
    print(f"Extracted {len(questions)} questions from full text:\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")


if __name__ == "__main__":
    main()
