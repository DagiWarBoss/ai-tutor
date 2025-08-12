import os, re, fitz, pandas as pd
from difflib import SequenceMatcher

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_headings(doc, chapter_number, topics):
    anchors = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4].strip()
            for topic in topics:
                tnum = topic['topic_number']
                ttitle = topic['name']
                # Match topic number
                if re.search(rf"^{chapter_number}\.\d+", text):
                    # Use fuzzy match for title
                    if similar(ttitle, text) > 0.6:
                        anchors.append({
                            'topic_number': tnum,
                            'title': ttitle,
                            'page': page_num,
                            'y': b[1]
                        })
    # sort anchors
    anchors.sort(key=lambda x: (x['page'], x['y']))
    return anchors

def extract_topic_contents(doc, anchors):
    all_blocks = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            text = b[4].strip()
            y0 = b[1]
            if text:
                all_blocks.append({'text': text, 'page': page_num, 'y': y0})
    # assign block text to topics
    for i, anchor in enumerate(anchors):
        start_page = anchor['page']
        start_y = anchor['y']
        end_page = anchors[i+1]['page'] if (i+1)<len(anchors) else float('inf')
        end_y = anchors[i+1]['y'] if (i+1)<len(anchors) else float('inf')
        topic_blocks = []
        for block in all_blocks:
            is_after = (block['page'] > start_page) or (block['page']==start_page and block['y']>start_y)
            is_before = (block['page'] < end_page) or (block['page']==end_page and block['y']<end_y)
            if is_after and is_before:
                topic_blocks.append(block['text'])
        anchor['content'] = "\n".join(topic_blocks)
    return anchors

def main():
    df = pd.read_csv(CSV_PATH)
    for pdf_filename in os.listdir(PDF_ROOT_FOLDER):
        if not pdf_filename.endswith('.pdf'):
            continue
        chapter_topics = df[df['chapter_file']==pdf_filename].to_dict('records')
        if not chapter_topics:
            print(f"[SKIP] No topic info for {pdf_filename}")
            continue
        pdf_path = os.path.join(PDF_ROOT_FOLDER, pdf_filename)
        doc = fitz.open(pdf_path)
        chap_num = str(chapter_topics[0]['chapter_number'])
        # Detect anchors
        anchors = find_headings(doc, chap_num, chapter_topics)
        if not anchors:
            print(f"[MISS] No anchors found for {pdf_filename}")
            continue
        # Extract topic contents
        topics_with_content = extract_topic_contents(doc, anchors)
        # Now, update DB with these contents (as in your code)
        # Loop topics_with_content and execute the UPDATE query
        doc.close()

main()
