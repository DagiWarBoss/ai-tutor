import pytesseract
from pdf2image import convert_from_path
from PIL import Image

pdf_path = "Some-Basic-Concepts-Of-Chemistry.pdf"
output_txt_path = "Some-Basic-Concepts-Of-Chemistry_OCR.txt"
# Use your real poppler path here
poppler_path = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\.venv\poppler-24.08.0\Library\bin"

# On Windows, set Tesseract location if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Convert PDF pages to images (using Poppler)
images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

all_text = []
for i, image in enumerate(images):
    text = pytesseract.image_to_string(image)
    all_text.append(text)

# Save the clean OCR text
full_text = '\n'.join(all_text)
with open(output_txt_path, "w", encoding="utf-8") as f:
    f.write(full_text)

print(f"OCR text written to {output_txt_path}!")
