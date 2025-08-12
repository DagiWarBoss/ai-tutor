import re

def extract_ncert_topics(chapter_text):
    """
    Extract NCERT topics using numbered headings as anchors.

    Returns: List of dicts: { 'topic_number', 'title', 'content' }
    """
    # This regex matches lines like "1.2 Nature of Matter", "1.2.3 Example of ...", etc.
    heading_re = re.compile(r'^(\d+(?:\.\d+)+)\s+([^\n]+)', re.MULTILINE)
    matches = list(heading_re.finditer(chapter_text))

    topics = []
    for i, match in enumerate(matches):
        topic_num = match.group(1)
        topic_title = match.group(2).strip()
        # Content: from this heading to the next, or EOF
        start = match.end()
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(chapter_text)
        content = chapter_text[start:end].strip()
        topics.append({
            'topic_number': topic_num,
            'title': topic_title,
            'content': content
        })
    return topics

# Example usage:
if __name__ == "__main__":
    with open("Some-Basic-Concepts-Of-Chemistry.txt", "r", encoding="utf-8") as f:
        chapter_text = f.read()

    topics = extract_ncert_topics(chapter_text)
    # Print summary
    for topic in topics:
        print(f"{topic['topic_number']} - {topic['title']}\n{'-'*60}")
        print(topic['content'][:400], "\n---\n")
