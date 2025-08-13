import os
import csv
import fitz  # PyMuPDF

# Root folder for all PDFs
PDF_ROOT_FOLDER = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\NCERT_PCM_ChapterWise"

# CSV with headings
CSV_FILE = "final_verified_topics.csv"

def extract_text_from_pdf(pdf_path):
    """Extracts all text from a PDF as a single string."""
    text = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text.append(page.get_text())
    return "\n".join(text)

def main():
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row["subject"]
            class_name = row["class"]
            chapter_file = row["chapter_file"]
            heading_number = row["heading_number"]
            heading_text = row["heading_text"]

            pdf_path = os.path.join(PDF_ROOT_FOLDER, subject, class_name, chapter_file)

            if os.path.exists(pdf_path):
                print(f"[FOUND] {pdf_path}")

                # Extract PDF text
                pdf_text = extract_text_from_pdf(pdf_path)

                # You could split by heading here if needed
                # For now, we just store the full PDF text
                data_entry = {
                    "subject": subject,
                    "class": class_name,
                    "chapter": chapter_file,
                    "heading_number": heading_number,
                    "heading_text": heading_text,
                    "content": pdf_text
                }

                # TODO: Replace with DB insertion code
                # insert_into_database(data_entry)
                print(f"  -> Ready to insert {heading_text}")

            else:
                print(f"[MISSING] {pdf_path}")

if __name__ == "__main__":
    main()
