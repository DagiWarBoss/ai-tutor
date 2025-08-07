import csv
import os

def populate_main_csv():
    """Populate the main extracted_headings_all_subjects.csv file with correct headings."""
    
    # Correct headings for Chemical Bonding chapter
    headings = [
        # Main topics
        ("4", "KÖssel-Lewis Approach to Chemical Bonding"),
        ("4.1", "Ionic or Electrovalent Bond"),
        ("4.2", "Bond Parameters"),
        ("4.3", "The Valence Shell Electron Pair Repulsion (VSEPR) Theory"),
        ("4.4", "Valence Bond Theory"),
        ("4.5", "Hybridisation"),
        ("4.6", "Molecular Orbital Theory"),
        ("4.7", "Bonding in Some Homonuclear Diatomic Molecules"),
        ("4.8", "Hydrogen Bonding"),
        
        # Sub-topics
        ("4.1.1", "Octet Rule"),
        ("4.1.2", "Covalent Bond"),
        ("4.1.3", "Lewis Representation of Simple Molecules"),
        ("4.1.4", "Formal Charge"),
        ("4.1.5", "Limitations of the Octet Rule"),
        
        ("4.2.1", "Lattice Enthalpy"),
        
        ("4.3.1", "Bond Length"),
        ("4.3.2", "Bond Angle"),
        ("4.3.3", "Bond Enthalpy"),
        ("4.3.4", "Bond Order"),
        ("4.3.5", "Resonance Structures"),
        ("4.3.6", "Polarity of Bonds"),
        
        ("4.4.1", "Valence Bond Theory Introduction"),
        ("4.4.2", "Overlap of Atomic Orbitals"),
        
        ("4.5.1", "Orbital Overlap Concept"),
        ("4.5.2", "Directional Properties of Bonds"),
        ("4.5.3", "Overlapping of Atomic Orbitals"),
        ("4.5.4", "Types of Overlapping and Nature of Covalent Bonds"),
        ("4.5.5", "Strength of Sigma and pi Bonds"),
        
        ("4.6.1", "Types of Hybridisation"),
        ("4.6.2", "Other Examples of sp3, sp2 and sp Hybridisation"),
        ("4.6.3", "Hybridisation of Elements involving d Orbitals"),
        
        ("4.7.1", "Formation of Molecular Orbitals"),
        ("4.7.2", "Conditions for the Combination of Atomic Orbitals"),
        ("4.7.3", "Types of Molecular Orbitals"),
        ("4.7.4", "Energy Level Diagram for Molecular Orbitals"),
        ("4.7.5", "Electronic Configuration and Molecular Behaviour"),
        
        ("4.8.1", "Intermolecular Forces"),
        ("4.8.2", "Types of Intermolecular Forces"),
        
        ("4.9.1", "Cause of Formation of Hydrogen Bond"),
        ("4.9.2", "Types of H-Bonds"),
    ]
    
    # Prepare data for CSV
    csv_data = []
    for heading_number, heading_text in headings:
        csv_data.append({
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Chemical Bonding And Molecular Structure.pdf',
            'chapter_number': '4',
            'heading_number': heading_number,
            'heading_text': heading_text
        })
    
    # Write to the main CSV file
    output_file = "extracted_headings_all_subjects.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['subject', 'class', 'chapter_file', 'chapter_number', 'heading_number', 'heading_text']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in csv_data:
            writer.writerow(row)
    
    print(f"Successfully populated {output_file} with {len(headings)} headings")
    print("\nHeadings added:")
    for heading_number, heading_text in headings:
        print(f"  - {heading_number} {heading_text}")

def main():
    """Main function to populate the main CSV."""
    populate_main_csv()

if __name__ == '__main__':
    main()
