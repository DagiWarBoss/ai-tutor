import fitz

def check_pdf_info(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        print(f"Checking: {pdf_path}")
        print(f"Number of pages: {len(doc)}")
        print(f"Metadata: {doc.metadata}")
        
        # Get text from first few pages
        text = ""
        for i in range(min(3, len(doc))):
            text += doc[i].get_text()
        
        # Look for copyright, edition, or year information
        lines = text.split('\n')
        for line in lines[:50]:  # Check first 50 lines
            if any(keyword in line.lower() for keyword in ['copyright', 'edition', '202', '201', '200', 'ncert']):
                print(f"Found relevant info: {line}")
        
        doc.close()
        print("-" * 50)
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")

# Check a few PDFs
pdfs_to_check = [
    'NCERT_PCM_ChapterWise/Chemistry/Class 11/Some Basic Concepts Of Chemistry.pdf',
    'NCERT_PCM_ChapterWise/Physics/Class 11/Laws Of Motion.pdf',
    'NCERT_PCM_ChapterWise/Maths/Class 11/Sets.pdf'
]

for pdf in pdfs_to_check:
    check_pdf_info(pdf)
