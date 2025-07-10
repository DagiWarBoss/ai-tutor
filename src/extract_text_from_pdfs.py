import os
import PyPDF2

# ✅ Set the base folder path (where Maths, Physics, Chemistry folders exist)
base_path = r"C:\Users\daksh\OneDrive\Dokumen\NCERT_PCM_ChapterWise"

# ✅ Map subjects to their folder paths
subject_dirs = {
    "Maths": os.path.join(base_path, "Maths"),
    "Physics": os.path.join(base_path, "Physics"),
    "Chemistry": os.path.join(base_path, "Chemistry")
}

# ✅ Output folder for .txt files
output_folder = os.path.join(base_path, "txt_outputs")
os.makedirs(output_folder, exist_ok=True)

# ✅ Process each subject
for subject, subject_path in subject_dirs.items():
    if not os.path.isdir(subject_path):
        print(f"❌ Folder not found: {subject_path}")
        continue

    subject_output = os.path.join(output_folder, subject)
    os.makedirs(subject_output, exist_ok=True)

    for filename in os.listdir(subject_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(subject_path, filename)
            txt_path = os.path.join(subject_output, filename.replace(".pdf", ".txt"))

            try:
                with open(pdf_path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)

                print(f"✅ Extracted: {filename}")
            except Exception as e:
                print(f"❌ Failed on {filename}: {e}")
