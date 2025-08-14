import pandas as pd

CSV_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics.csv"
OUTPUT_PATH = r"C:\Users\daksh\OneDrive\Dokumen\ai-tutor\backend\final_verified_topics_spaces.csv"

df = pd.read_csv(CSV_PATH, dtype=str)

# 🔹 Replace hyphen with space in chapter_file
df['chapter_file'] = df['chapter_file'].fillna('').str.replace('-', ' ', regex=False)

df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')

print(f"✅ Saved with spaces instead of hyphens: {OUTPUT_PATH}")
