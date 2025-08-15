import os
import re

# Path to the OCR text file of the chapter
OCR_TEXT_PATH = r"ocr_cache\Chemical Bonding And Molecular Structure.txt"

def extract_exercise_questions(file_path):
    """
    Extract full questions from the Exercises section in an OCR text file.

    A question:
      - Starts with a line ending with '?'
      - May span multiple lines until the next question starts or section ends
    """
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_exercises = False
    current_question = []
    question_start_pattern = re.compile(r".*\?$")  # Line ending with '?'
    all_caps_header_pattern = re.compile(r"^[A-Z0-9 \-']{5,}$")

    for line in lines:
        line_strip = line.strip()

        # --- Detect start of EXERCISES section ---
        if not in_exercises and re.search(r"\bEXERCISES\b", line_strip, re.IGNORECASE):
            in_exercises = True
            continue

        if in_exercises:
            # --- Detect end of exercises section ---
            if all_caps_header_pattern.match(line_strip) and not "?" in line_strip:
                # Save any last accumulated question
                if current_question:
                    questions.append(" ".join(current_question).strip())
                break

            # --- If line starts a new question ---
            if question_start_pattern.match(line_strip):
                # Save the previous question before starting a new one
                if current_question:
                    questions.append(" ".join(current_question).strip())
                    current_question = []
                current_question.append(line_strip)
            else:
                # Check if we are inside a question (continuation lines)
                if current_question:
                    current_question.append(line_strip)

    # Save the last question if any
    if current_question:
        questions.append(" ".join(current_question).strip())

    return questions


def main():
    if not os.path.exists(OCR_TEXT_PATH):
        print(f"OCR text file not found: {OCR_TEXT_PATH}")
        return

    questions = extract_exercise_questions(OCR_TEXT_PATH)
    print(f"Extracted {len(questions)} questions from Exercises section:\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")


if __name__ == "__main__":
    main()
