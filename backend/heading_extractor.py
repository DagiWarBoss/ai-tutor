import os
import fitz  # PyMuPDF
import re
from typing import List, Tuple, Dict

class HeadingExtractor:
    """Utility class for extracting chapter headings from PDF files."""
    
    def __init__(self, pdf_root_folder: str = "NCERT_PCM_ChapterWise"):
        self.pdf_root_folder = pdf_root_folder
        self.script_dir = os.path.dirname(__file__)
        
    def extract_chapter_headings(self, pdf_path: str, chapter_number: str) -> List[Tuple[str, str]]:
        """
        Extract headings from a PDF chapter.
        
        Args:
            pdf_path: Path to the PDF file
            chapter_number: The chapter number to look for (e.g., "4", "7.1")
            
        Returns:
            List of tuples (number, heading_text)
        """
        doc = fitz.open(pdf_path)
        lines = []
        for page_num in range(doc.page_count):
            lines.extend(doc[page_num].get_text().split('\n'))
        headings = []
        i = 0
        
        # Pattern: Allow up to 5 decimals, but only at line start (not mid)
        pat = re.compile(rf"^\s*({chapter_number}(?:\.\d+){{0,5}})[\s\.:;\-)]+(.*)$")
        
        while i < len(lines):
            line = lines[i].strip()
            match = pat.match(line)
            if match:
                num, text = match.group(1).strip(), match.group(2).strip()
                
                # If text is empty or very short, look ahead for continuation
                if not text or len(text.split()) < 2:
                    # Look ahead up to 3 lines for continuation
                    for look_ahead in range(1, 4):
                        if i + look_ahead < len(lines):
                            next_line = lines[i + look_ahead].strip()
                            # Skip empty lines and lines that start with numbers (likely new headings)
                            if next_line and not re.match(r'^\d+', next_line):
                                # If next line starts with uppercase and doesn't look like a new heading
                                if next_line and next_line[0].isupper():
                                    # Check if this looks like a heading continuation or explanatory text
                                    words = next_line.split()
                                    
                                    # If it's short and doesn't start with common explanatory words
                                    if len(words) <= 8 and not any(word.lower() in ['the', 'and', 'of', 'in', 'to', 'for', 'with', 'by', 'is', 'are', 'was', 'were'] for word in words[:2]):
                                        if text:
                                            text = text + " " + next_line
                                        else:
                                            text = next_line
                                        i += look_ahead
                                        break
                                    else:
                                        # This looks like explanatory text, stop here
                                        break
                                
                                # Also check if next line continues the current text (lowercase continuation)
                                elif next_line and next_line[0].islower() and text:
                                    # Only add if it's a short continuation (likely part of the heading)
                                    if len(next_line.split()) <= 4:
                                        text = text + " " + next_line
                                        i += look_ahead
                                        break
                                    else:
                                        # Too long, likely explanatory text
                                        break
                
                # Only add if we have meaningful text
                if text and len(text.strip()) > 0:
                    headings.append((num, text.strip()))
            i += 1
        doc.close()
        return headings
    
    def post_filter(self, headings: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Filter and clean extracted headings.
        
        Args:
            headings: List of (number, text) tuples
            
        Returns:
            Filtered list of headings
        """
        cleaned = []
        # Remove obvious non-headings
        BAD_STARTS = (
            'table', 'fig', 'exercise', 'problem', 'example', 'write', 'draw',
        )
        # Remove obvious non-headings
        BAD_CONTAINS = ('equation', 'value', 'define', 'distinguish', 'write', 'calculate')
        
        for num, text in headings:
            t = text.strip()
            words = t.split()
            
            # Skip if no text
            if not t:
                continue
                
            # Skip if too short or too long
            if len(words) < 2 or len(words) > 15:
                continue
                
            # Skip if it's just a number (like "4 1", "4 2", etc.)
            if len(words) == 1 and words[0].isdigit():
                continue
                
            # Skip if it looks like a question (starts with question words)
            if any(t.lower().startswith(q) for q in ['define', 'distinguish', 'write', 'calculate', 'explain', 'how', 'why', 'what']):
                continue
                
            # Only exclude very obvious non-headings
            if any(t.lower().startswith(bad) for bad in BAD_STARTS):
                continue
                
            # Very minimal BAD_CONTAINS filtering
            if any(bad in t.lower() for bad in BAD_CONTAINS):
                continue
                
            # Don't allow headings ending with ":" (often captions)
            if t.endswith(':'):
                continue
                
            # Additional check: skip if the heading is just the number
            if t.lower() == num.lower():
                continue
                
            # Skip if it's just a number followed by nothing meaningful
            if len(words) == 2 and words[0].isdigit() and len(words[1]) < 3:
                continue
                
            cleaned.append((num, text))
        return cleaned
    
    def extract_all_chapter_headings(self, subject: str, class_name: str, chapter_name: str, chapter_number: str) -> List[Tuple[str, str]]:
        """
        Extract headings from a specific chapter.
        
        Args:
            subject: Subject name (e.g., "Chemistry", "Physics", "Maths")
            class_name: Class name (e.g., "Class 11", "Class 12")
            chapter_name: Chapter PDF filename
            chapter_number: Chapter number to extract
            
        Returns:
            List of filtered headings
        """
        pdf_path = os.path.join(
            self.script_dir, self.pdf_root_folder,
            subject, class_name, chapter_name
        )
        
        if not os.path.exists(pdf_path):
            print(f"PDF file not found: {pdf_path}")
            return []
        
        headings = self.extract_chapter_headings(pdf_path, chapter_number)
        filtered_headings = self.post_filter(headings)
        return filtered_headings
    
    def get_available_chapters(self) -> Dict[str, List[str]]:
        """
        Get a list of all available chapters organized by subject and class.
        
        Returns:
            Dictionary with structure: {subject: {class_name: [chapter_files]}}
        """
        chapters = {}
        pdf_folder = os.path.join(self.script_dir, self.pdf_root_folder)
        
        if not os.path.exists(pdf_folder):
            print(f"PDF folder not found: {pdf_folder}")
            return chapters
        
        for subject in os.listdir(pdf_folder):
            subject_path = os.path.join(pdf_folder, subject)
            if os.path.isdir(subject_path):
                chapters[subject] = {}
                for class_name in os.listdir(subject_path):
                    class_path = os.path.join(subject_path, class_name)
                    if os.path.isdir(class_path):
                        chapter_files = [f for f in os.listdir(class_path) if f.endswith('.pdf')]
                        chapters[subject][class_name] = chapter_files
        
        return chapters

def main():
    """Test the heading extractor with the Chemical Bonding chapter."""
    extractor = HeadingExtractor()
    
    # Test with the Chemical Bonding chapter
    subject = "Chemistry"
    class_name = "Class 11"
    chapter_name = "Chemical Bonding And Molecular Structure.pdf"
    chapter_number = "4"
    
    headings = extractor.extract_all_chapter_headings(subject, class_name, chapter_name, chapter_number)
    
    print(f"\nMatched clean candidate headings for '{chapter_name}':")
    for num, text in headings:
        print(f"  - {num} {text}")
    print(f"\nTotal filtered matches: {len(headings)}")

if __name__ == '__main__':
    main()
