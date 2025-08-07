import os
import csv
from dotenv import load_dotenv
from heading_extractor import HeadingExtractor

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

def test_extraction_with_sample_chapters():
    """Test the extraction with a few sample chapters."""
    extractor = HeadingExtractor()
    
    # Test with a few sample chapters
    test_cases = [
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Chemical Bonding And Molecular Structure.pdf',
            'chapter_number': '4'
        },
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Laws Of Motion.pdf',
            'chapter_number': '5'
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Trigonometric Functions.pdf',
            'chapter_number': '3'
        }
    ]
    
    all_headings = []
    
    print("Testing extraction with sample chapters...")
    
    for test_case in test_cases:
        print(f"\nProcessing: {test_case['subject']} - {test_case['class']} - {test_case['chapter_file']}")
        
        try:
            headings = extractor.extract_all_chapter_headings(
                test_case['subject'],
                test_case['class'],
                test_case['chapter_file'],
                test_case['chapter_number']
            )
            
            # Add to results
            for num, text in headings:
                all_headings.append({
                    'subject': test_case['subject'],
                    'class': test_case['class'],
                    'chapter_file': test_case['chapter_file'],
                    'chapter_number': test_case['chapter_number'],
                    'heading_number': num,
                    'heading_text': text
                })
            
            print(f"  Found {len(headings)} headings")
            
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # Save to CSV
    if all_headings:
        output_file = "test_extracted_headings.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['subject', 'class', 'chapter_file', 'chapter_number', 'heading_number', 'heading_text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for heading in all_headings:
                writer.writerow(heading)
        
        print(f"\nTest extraction complete! Found {len(all_headings)} headings total.")
        print(f"Results saved to: {output_file}")
        
        # Show sample results
        print("\nSample results:")
        for i, heading in enumerate(all_headings[:10]):
            print(f"  {i+1}. {heading['heading_number']} {heading['heading_text']}")
    else:
        print("\nNo headings were extracted!")

def main():
    """Main function to run the test extraction."""
    test_extraction_with_sample_chapters()

if __name__ == '__main__':
    main()
