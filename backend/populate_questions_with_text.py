import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Function to convert PDF pages to images at specified DPI
def pdf_to_images(pdf_path, dpi=400):
    return convert_from_path(pdf_path, dpi=dpi)

# OCR function for an image or list of images
def ocr_images(images):
    text_all = []
    for img in images:
        text = pytesseract.image_to_string(img, lang='eng')
        text_all.append(text)
    return "\n".join(text_all)

# Specify your file paths
pdf_file = 'your_file.pdf'

# Step 1: Convert PDF to images at 400 DPI (recommended for clean textbook scans)
images = pdf_to_images(pdf_file, dpi=400)

# Step 2: OCR extract text from images
ocr_text = ocr_images(images)

# Step 3: Save OCR output to a file for inspection
with open('ocr_output.txt', 'w', encoding='utf-8') as f:
    f.write(ocr_text)

print("OCR text extraction completed. Check ocr_output.txt for results.")
