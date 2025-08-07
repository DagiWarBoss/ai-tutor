import os
import csv
from dotenv import load_dotenv
from heading_extractor import HeadingExtractor

# --- Load Environment Variables ---
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

def extract_headings_from_all_chapters():
    """Extract headings from all available chapters and save to CSV."""
    extractor = HeadingExtractor()
    
    # Get all available chapters
    chapters = extractor.get_available_chapters()
    
    if not chapters:
        print("No chapters found!")
        return
    
    all_headings = []
    
    # Chapter number mappings (you may need to adjust these based on your PDFs)
    chapter_numbers = {
        # Chemistry Class 11
        "Some Basic Concepts Of Chemistry.pdf": "1",
        "Structure Of Atom.pdf": "2", 
        "Classification Of Elements And Periodicity.pdf": "3",
        "Chemical Bonding And Molecular Structure.pdf": "4",
        "Thermodynamics.pdf": "6",
        "Equilibrium.pdf": "7",
        "Redox Reactions.pdf": "8",
        "Hydrocarbons.pdf": "13",
        "Organic Chemistry Basics.pdf": "12",
        
        # Chemistry Class 12
        "Haloalkanes And Haloarenes.pdf": "10",
        "Alcohol Phenols Ethers.pdf": "11",
        "Aldehydes, Ketones And Carboxylic Acid.pdf": "12",
        "Amines.pdf": "13",
        "Biomolecules.pdf": "14",
        "Chemical Kinetics.pdf": "4",
        "Coordination Compounds.pdf": "9",
        "D And F Block.pdf": "8",
        "Electrochemistry.pdf": "3",
        "Solutions.pdf": "2",
        
        # Physics Class 11
        "Units And Measurements.pdf": "2",
        "Motion In A Straight Line.pdf": "3",
        "Motion In A Plane.pdf": "4",
        "Laws Of Motion.pdf": "5",
        "Work Energy Power.pdf": "6",
        "System Of Particles And Rotational Motion.pdf": "7",
        "Gravitation.pdf": "8",
        "Mechanical Properties Of Solids.pdf": "9",
        "Mechanical Properties Of Fluids.pdf": "10",
        "Thermal Properties Of Matter.pdf": "11",
        "Thermodynamics.pdf": "12",
        "Kinetic Theory.pdf": "13",
        "Oscillations.pdf": "14",
        "Waves.pdf": "15",
        
        # Physics Class 12
        "Electric Charges And Fields.pdf": "1",
        "Electrostatic Potential And Capacitance.pdf": "2",
        "Current Electricity.pdf": "3",
        "Moving Charges And Magnetism.pdf": "4",
        "Magnetism And Matter.pdf": "5",
        "Electromagnetic Induction.pdf": "6",
        "Alternating Current.pdf": "7",
        "Electromagnetic Waves.pdf": "8",
        "Ray Optics.pdf": "9",
        "Wave Optics.pdf": "10",
        "Dual Nature Of Radiation And Matter.pdf": "11",
        "Atoms.pdf": "12",
        "Nuclei.pdf": "13",
        "SemiConductor Electronics.pdf": "14",
        
        # Maths Class 11
        "Sets.pdf": "1",
        "Relations And Functions.pdf": "2",
        "Trigonometric Functions.pdf": "3",
        "Complex Numbers And Quadratic Equations.pdf": "5",
        "Linear Inequalities.pdf": "6",
        "Permutations And Combinations.pdf": "7",
        "Binomial Theorem.pdf": "8",
        "Sequences And Series.pdf": "9",
        "Straight Lines.pdf": "10",
        "Conic Sections.pdf": "11",
        "Introduction to Three Dimensional Geometry.pdf": "12",
        "Limits And Derivatives.pdf": "13",
        "Statistics.pdf": "15",
        "Probability.pdf": "16",
        
        # Maths Class 12
        "Relations And Functions.pdf": "1",
        "Inverse Trigonometric Functions.pdf": "2",
        "Matrices.pdf": "3",
        "Determinants.pdf": "4",
        "Contunuity And Differentiability.pdf": "5",
        "Application Of Derivatives.pdf": "6",
        "Integrals.pdf": "7",
        "Application Of Integrals.pdf": "8",
        "Differential Equations.pdf": "9",
        "Vector Algebra.pdf": "10",
        "Three Dimensional Geometry.pdf": "11",
        "Linear Programming.pdf": "12",
        "Probability.pdf": "13",
        "Infinite Series.pdf": "14",
        "Proofs In Mathematics.pdf": "15"
    }
    
    print("Starting extraction of headings from all chapters...")
    
    for subject in chapters:
        print(f"\nProcessing subject: {subject}")
        for class_name in chapters[subject]:
            print(f"  Processing class: {class_name}")
            for chapter_file in chapters[subject][class_name]:
                # Get chapter number from mapping
                chapter_number = chapter_numbers.get(chapter_file, "1")  # Default to "1" if not found
                
                print(f"    Processing chapter: {chapter_file} (Chapter {chapter_number})")
                
                try:
                    headings = extractor.extract_all_chapter_headings(
                        subject, class_name, chapter_file, chapter_number
                    )
                    
                    # Add to results
                    for num, text in headings:
                        all_headings.append({
                            'subject': subject,
                            'class': class_name,
                            'chapter_file': chapter_file,
                            'chapter_number': chapter_number,
                            'heading_number': num,
                            'heading_text': text
                        })
                    
                    print(f"      Found {len(headings)} headings")
                    
                except Exception as e:
                    print(f"      ERROR processing {chapter_file}: {e}")
    
    # Save to CSV
    if all_headings:
        output_file = "extracted_headings_all_subjects.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['subject', 'class', 'chapter_file', 'chapter_number', 'heading_number', 'heading_text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for heading in all_headings:
                writer.writerow(heading)
        
        print(f"\nExtraction complete! Found {len(all_headings)} headings total.")
        print(f"Results saved to: {output_file}")
    else:
        print("\nNo headings were extracted!")

def main():
    """Main function to run the extraction."""
    extract_headings_from_all_chapters()

if __name__ == '__main__':
    main()
