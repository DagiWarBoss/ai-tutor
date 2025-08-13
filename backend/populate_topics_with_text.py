import os
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# Configure Tesseract executable path if needed
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Update path if necessary

def extract_text_from_pdf(pdf_path):
    text_data = []
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            text_data.append(text)
        else:
            # Convert page to image, then OCR if no text found
            images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1)
            for img in images:
                text = pytesseract.image_to_string(img)
                text_data.append(text)
    return text_data

def connect_db():
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )
    return conn

def insert_text_data(conn, chapter_name, page_texts):
    with conn.cursor() as curs:
        records = [(chapter_name, idx + 1, text) for idx, text in enumerate(page_texts)]
        execute_values(curs,
                       "INSERT INTO ncert_text_data (chapter, page_number, text_content) VALUES %s",
                       records)
    conn.commit()

def main():
    pdf_path = 'path_to_your_ncert_chapter.pdf'  # Specify your PDF file here
    chapter_name = 'Chapter 1: Example Chapter'  # Modify as needed

    print(f'Extracting text from {pdf_path}...')
    page_texts = extract_text_from_pdf(pdf_path)

    print('Connecting to database...')
    conn = connect_db()

    print('Inserting text data into database...')
    insert_text_data(conn, chapter_name, page_texts)

    conn.close()
    print('Process completed successfully.')

if __name__ == '__main__':
    main()
