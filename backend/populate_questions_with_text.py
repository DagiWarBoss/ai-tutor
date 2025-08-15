import os
import re

# Path to the OCR text file of the chapter (cached OCR text)
OCR_TEXT_PATH = r"ocr_cache\Chemical Bonding And Molecular Structure.txt"

def extract_exercise_questions(file_path):
    """
    Extract questions that appear after the Exercises section.
    Assumes Exercises section starts with a line containing 'EXERCISES' (case-insensitive).
    Collects all lines ending with '?' until a new all-caps header or end of file.
    """
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_exercises = False
    question_pattern = re.compile(r".*\?$")  # Lines ending with '?'

    for line in lines:
        line_strip = line.strip()

        # Detect start of Exercises section
        if not in_exercises and re.search(r"\bEXERCISES\b", line_strip, re.IGNORECASE):
            in_exercises = True
            continue

        if in_exercises:
            # Stop if next major section header found (all caps, no question mark)
            if re.match(r"^[A-Z \-\']{5,}$", line_strip) and not "?" in line_strip:
                break

            # Capture questions - lines ending with '?'
            if question_pattern.match(line_strip):
                questions.append(line_strip)

    return questions


def main():
    if not os.path.exists(OCR_TEXT_PATH):
        print(f"OCR text file not found: {OCR_TEXT_PATH}")
        return

    questions = extract_exercise_questions(OCR_TEXT_PATH)
    print(f"Extracted {len(questions)} questions from Exercises section:\n")
    for i, question in enumerate(questions, 1):
        print(f"{i}. {question}")


if __name__ == "__main__":
    main()
