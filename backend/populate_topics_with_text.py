import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os

# Set these paths as needed
pdf_path = "Some-Basic-Concepts-Of-Chemistry.pdf"
output_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"
poppler_path = r"C:\path\to\poppler\bin"  # Only needed on Windows

# Point pytesseract to the tesseract binary if necessary (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Convert PDF pages to images
images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

all_text = []
for i, image in enumerate(images):
    text = pytesseract.image_to_string(image)
    text = text.replace('-\n', '')  # Fixes broken words on line breaks
    all_text.append(text)

full_text = '\n'.join(all_text)
with open(output_txt_path, "w", encoding="utf-8") as f:
    f.write(full_text)

print(f"OCR text written to {output_txt_path}!")
