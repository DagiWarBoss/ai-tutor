import csv
import os

def populate_all_chapters():
    """Populate the CSV with all chapters and their topics."""
    
    # All chapters with their topics
    all_chapters = [
        # Chemistry Class 11
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Some Basic Concepts Of Chemistry.pdf',
            'chapter_number': '1',
            'headings': [
                ("1", "Some Basic Concepts of Chemistry"),
                ("1.1", "Importance of Chemistry"),
                ("1.2", "Nature of Matter"),
                ("1.3", "Properties of Matter and their Measurement"),
                ("1.4", "Uncertainty in Measurement"),
                ("1.5", "Laws of Chemical Combinations"),
                ("1.6", "Dalton's Atomic Theory"),
                ("1.7", "Atomic and Molecular Masses"),
                ("1.8", "Mole Concept and Molar Masses"),
                ("1.9", "Percentage Composition"),
                ("1.10", "Stoichiometry and Stoichiometric Calculations"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Structure Of Atom.pdf',
            'chapter_number': '2',
            'headings': [
                ("2", "Structure of Atom"),
                ("2.1", "Discovery of Sub-atomic Particles"),
                ("2.2", "Atomic Models"),
                ("2.3", "Developments Leading to the Bohr's Model of Atom"),
                ("2.4", "Bohr's Model for Hydrogen Atom"),
                ("2.5", "Towards Quantum Mechanical Model of the Atom"),
                ("2.6", "Quantum Mechanical Model of Atom"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Classification Of Elements And Periodicity.pdf',
            'chapter_number': '3',
            'headings': [
                ("3", "Classification of Elements and Periodicity in Properties"),
                ("3.1", "Why do we need to classify elements?"),
                ("3.2", "Genesis of Periodic Classification"),
                ("3.3", "Modern Periodic Law and the present form of the Periodic Table"),
                ("3.4", "Nomenclature of Elements with Atomic Numbers > 100"),
                ("3.5", "Electronic Configurations of Elements and the Periodic Table"),
                ("3.6", "Electronic Configurations and Types of Elements: s-, p-, d-, f- Blocks"),
                ("3.7", "Periodic Trends in Properties of Elements"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Chemical Bonding And Molecular Structure.pdf',
            'chapter_number': '4',
            'headings': [
                ("4", "KÖssel-Lewis Approach to Chemical Bonding"),
                ("4.1", "Ionic or Electrovalent Bond"),
                ("4.2", "Bond Parameters"),
                ("4.3", "The Valence Shell Electron Pair Repulsion (VSEPR) Theory"),
                ("4.4", "Valence Bond Theory"),
                ("4.5", "Hybridisation"),
                ("4.6", "Molecular Orbital Theory"),
                ("4.7", "Bonding in Some Homonuclear Diatomic Molecules"),
                ("4.8", "Hydrogen Bonding"),
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
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Thermodynamics.pdf',
            'chapter_number': '6',
            'headings': [
                ("6", "Thermodynamics"),
                ("6.1", "Thermodynamic Terms"),
                ("6.2", "Applications"),
                ("6.3", "Measurement of ΔU and ΔH: Calorimetry"),
                ("6.4", "Enthalpy Change, ΔrH of a Reaction – Reaction Enthalpy"),
                ("6.5", "Enthalpies for Different Types of Reactions"),
                ("6.6", "Spontaneity"),
                ("6.7", "Gibbs Energy Change and Equilibrium"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Equilibrium.pdf',
            'chapter_number': '7',
            'headings': [
                ("7", "Equilibrium"),
                ("7.1", "Equilibrium in Physical Processes"),
                ("7.2", "Equilibrium in Chemical Processes – Dynamic Equilibrium"),
                ("7.3", "Law of Chemical Equilibrium and Equilibrium Constant"),
                ("7.4", "Heterogeneous Equilibria"),
                ("7.5", "Applications of Equilibrium Constants"),
                ("7.6", "Factors Affecting Equilibria"),
                ("7.7", "Ionic Equilibrium in Solution"),
                ("7.8", "Ionization of Acids and Bases"),
                ("7.9", "Buffer Solutions"),
                ("7.10", "Solubility Equilibria of Sparingly Soluble Salts"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Redox Reactions.pdf',
            'chapter_number': '8',
            'headings': [
                ("8", "Redox Reactions"),
                ("8.1", "Classical Idea of Redox Reactions-Oxidation and Reduction Reactions"),
                ("8.2", "Redox Reactions in Terms of Electron Transfer Reactions"),
                ("8.3", "Competitive Electron Transfer Reactions"),
                ("8.4", "Oxidation Number"),
                ("8.5", "Types of Redox Reactions"),
                ("8.6", "Balancing of Redox Reactions"),
                ("8.7", "Redox Reactions as the Basis for Titrations"),
                ("8.8", "Limitations of Concept of Oxidation Number"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Hydrocarbons.pdf',
            'chapter_number': '13',
            'headings': [
                ("13", "Hydrocarbons"),
                ("13.1", "Classification"),
                ("13.2", "Alkanes"),
                ("13.3", "Alkenes"),
                ("13.4", "Alkynes"),
                ("13.5", "Aromatic Hydrocarbon"),
                ("13.6", "Carcinogenicity and Toxicity"),
            ]
        },
        {
            'subject': 'Chemistry',
            'class': 'Class 11',
            'chapter_file': 'Organic Chemistry Basics.pdf',
            'chapter_number': '12',
            'headings': [
                ("12", "Organic Chemistry – Some Basic Principles and Techniques"),
                ("12.1", "General Introduction"),
                ("12.2", "Tetravalence of Carbon: Shapes of Organic Compounds"),
                ("12.3", "Structural Representations of Organic Compounds"),
                ("12.4", "Classification of Organic Compounds"),
                ("12.5", "Nomenclature of Organic Compounds"),
                ("12.6", "Isomerism"),
                ("12.7", "Fundamental Concepts in Organic Reaction Mechanism"),
                ("12.8", "Methods of Purification of Organic Compounds"),
                ("12.9", "Qualitative Analysis of Organic Compounds"),
                ("12.10", "Quantitative Analysis"),
            ]
        },
        
        # Physics Class 11
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Units And Measurements.pdf',
            'chapter_number': '2',
            'headings': [
                ("2", "Units and Measurements"),
                ("2.1", "Introduction"),
                ("2.2", "The International System of Units"),
                ("2.3", "Measurement of Length"),
                ("2.4", "Measurement of Mass"),
                ("2.5", "Measurement of Time"),
                ("2.6", "Accuracy, Precision of Instruments and Errors in Measurement"),
                ("2.7", "Significant Figures"),
                ("2.8", "Dimensions of Physical Quantities"),
                ("2.9", "Dimensional Formulae and Dimensional Equations"),
                ("2.10", "Dimensional Analysis and its Applications"),
            ]
        },
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Motion In A Straight Line.pdf',
            'chapter_number': '3',
            'headings': [
                ("3", "Motion in a Straight Line"),
                ("3.1", "Introduction"),
                ("3.2", "Position, Path Length and Displacement"),
                ("3.3", "Average Velocity and Average Speed"),
                ("3.4", "Instantaneous Velocity and Speed"),
                ("3.5", "Acceleration"),
                ("3.6", "Kinematic Equations for Uniformly Accelerated Motion"),
                ("3.7", "Relative Velocity"),
            ]
        },
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Motion In A Plane.pdf',
            'chapter_number': '4',
            'headings': [
                ("4", "Motion in a Plane"),
                ("4.1", "Introduction"),
                ("4.2", "Scalars and Vectors"),
                ("4.3", "Multiplication of Vectors by Real Numbers"),
                ("4.4", "Addition and Subtraction of Vectors – Graphical Method"),
                ("4.5", "Resolution of Vectors"),
                ("4.6", "Vector Addition – Analytical Method"),
                ("4.7", "Motion in a Plane"),
                ("4.8", "Motion in a Plane with Constant Acceleration"),
                ("4.9", "Relative Velocity in Two Dimensions"),
                ("4.10", "Projectile Motion"),
                ("4.11", "Uniform Circular Motion"),
            ]
        },
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Laws Of Motion.pdf',
            'chapter_number': '5',
            'headings': [
                ("5", "Laws of Motion"),
                ("5.1", "Introduction"),
                ("5.2", "Aristotle's Fallacy"),
                ("5.3", "The Law of Inertia"),
                ("5.4", "Newton's First Law of Motion"),
                ("5.5", "Newton's Second Law of Motion"),
                ("5.6", "Newton's Third Law of Motion"),
                ("5.7", "Conservation of Momentum"),
                ("5.8", "Equilibrium of a Particle"),
                ("5.9", "Common Forces in Mechanics"),
                ("5.10", "Circular Motion"),
                ("5.11", "Solving Problems in Mechanics"),
            ]
        },
        {
            'subject': 'Physics',
            'class': 'Class 11',
            'chapter_file': 'Work Energy Power.pdf',
            'chapter_number': '6',
            'headings': [
                ("6", "Work, Energy and Power"),
                ("6.1", "Introduction"),
                ("6.2", "Notions of Work and Kinetic Energy: The Work-Energy Theorem"),
                ("6.3", "Work"),
                ("6.4", "Kinetic Energy"),
                ("6.5", "Work Done by a Variable Force"),
                ("6.6", "The Work-Energy Theorem for a Variable Force"),
                ("6.7", "The Concept of Potential Energy"),
                ("6.8", "The Conservation of Mechanical Energy"),
                ("6.9", "The Potential Energy of a Spring"),
                ("6.10", "Various Forms of Energy: The Law of Conservation of Energy"),
                ("6.11", "Power"),
                ("6.12", "Collisions"),
            ]
        },
        
        # Maths Class 11
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Sets.pdf',
            'chapter_number': '1',
            'headings': [
                ("1", "Sets"),
                ("1.1", "Introduction"),
                ("1.2", "Sets and their Representations"),
                ("1.3", "The Empty Set"),
                ("1.4", "Finite and Infinite Sets"),
                ("1.5", "Equal Sets"),
                ("1.6", "Subsets"),
                ("1.7", "Power Set"),
                ("1.8", "Universal Set"),
                ("1.9", "Venn Diagrams"),
                ("1.10", "Operations on Sets"),
                ("1.11", "Complement of a Set"),
                ("1.12", "Practical Problems on Union and Intersection of Two Sets"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Relations And Functions.pdf',
            'chapter_number': '2',
            'headings': [
                ("2", "Relations and Functions"),
                ("2.1", "Introduction"),
                ("2.2", "Cartesian Products of Sets"),
                ("2.3", "Relations"),
                ("2.4", "Functions"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Trigonometric Functions.pdf',
            'chapter_number': '3',
            'headings': [
                ("3", "Trigonometric Functions"),
                ("3.1", "Introduction"),
                ("3.2", "Angles"),
                ("3.3", "Trigonometric Functions"),
                ("3.4", "Trigonometric Functions of Sum and Difference of Two Angles"),
                ("3.5", "Trigonometric Equations"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Complex Numbers And Quadratic Equations.pdf',
            'chapter_number': '5',
            'headings': [
                ("5", "Complex Numbers and Quadratic Equations"),
                ("5.1", "Introduction"),
                ("5.2", "Complex Numbers"),
                ("5.3", "Algebra of Complex Numbers"),
                ("5.4", "The Modulus and the Conjugate of a Complex Number"),
                ("5.5", "Argand Plane and Polar Representation"),
                ("5.6", "Quadratic Equations"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Linear Inequalities.pdf',
            'chapter_number': '6',
            'headings': [
                ("6", "Linear Inequalities"),
                ("6.1", "Introduction"),
                ("6.2", "Inequalities"),
                ("6.3", "Algebraic Solutions of Linear Inequalities in One Variable and their Graphical Representation"),
                ("6.4", "Graphical Solution of Linear Inequalities in Two Variables"),
                ("6.5", "Solution of System of Linear Inequalities in Two Variables"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Permutations And Combinations.pdf',
            'chapter_number': '7',
            'headings': [
                ("7", "Permutations and Combinations"),
                ("7.1", "Introduction"),
                ("7.2", "Fundamental Principle of Counting"),
                ("7.3", "Permutations"),
                ("7.4", "Combinations"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Binomial Theorem.pdf',
            'chapter_number': '8',
            'headings': [
                ("8", "Binomial Theorem"),
                ("8.1", "Introduction"),
                ("8.2", "Binomial Theorem for Positive Integral Indices"),
                ("8.3", "General and Middle Terms"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Sequences And Series.pdf',
            'chapter_number': '9',
            'headings': [
                ("9", "Sequences and Series"),
                ("9.1", "Introduction"),
                ("9.2", "Sequences"),
                ("9.3", "Series"),
                ("9.4", "Arithmetic Progression (A.P.)"),
                ("9.5", "Geometric Progression (G.P.)"),
                ("9.6", "Relationship Between A.M. and G.M."),
                ("9.7", "Sum to n terms of Special Series"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Straight Lines.pdf',
            'chapter_number': '10',
            'headings': [
                ("10", "Straight Lines"),
                ("10.1", "Introduction"),
                ("10.2", "Slope of a Line"),
                ("10.3", "Various Forms of the Equation of a Line"),
                ("10.4", "General Equation of a Line"),
                ("10.5", "Distance of a Point From a Line"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Conic Sections.pdf',
            'chapter_number': '11',
            'headings': [
                ("11", "Conic Sections"),
                ("11.1", "Introduction"),
                ("11.2", "Sections of a Cone"),
                ("11.3", "Circle"),
                ("11.4", "Parabola"),
                ("11.5", "Ellipse"),
                ("11.6", "Hyperbola"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Introduction to Three Dimensional Geometry.pdf',
            'chapter_number': '12',
            'headings': [
                ("12", "Introduction to Three Dimensional Geometry"),
                ("12.1", "Introduction"),
                ("12.2", "Coordinate Axes and Coordinate Planes in Three Dimensional Space"),
                ("12.3", "Coordinates of a Point in Space"),
                ("12.4", "Distance between Two Points"),
                ("12.5", "Section Formula"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Limits And Derivatives.pdf',
            'chapter_number': '13',
            'headings': [
                ("13", "Limits and Derivatives"),
                ("13.1", "Introduction"),
                ("13.2", "Intuitive Idea of Derivatives"),
                ("13.3", "Limits"),
                ("13.4", "Limits of Trigonometric Functions"),
                ("13.5", "Derivatives"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Statistics.pdf',
            'chapter_number': '15',
            'headings': [
                ("15", "Statistics"),
                ("15.1", "Introduction"),
                ("15.2", "Measures of Dispersion"),
                ("15.3", "Range"),
                ("15.4", "Mean Deviation"),
                ("15.5", "Variance and Standard Deviation"),
                ("15.6", "Analysis of Frequency Distributions"),
            ]
        },
        {
            'subject': 'Maths',
            'class': 'Class 11',
            'chapter_file': 'Probability.pdf',
            'chapter_number': '16',
            'headings': [
                ("16", "Probability"),
                ("16.1", "Introduction"),
                ("16.2", "Random Experiments"),
                ("16.3", "Event"),
                ("16.4", "Axiomatic Approach to Probability"),
            ]
        },
    ]
    
    # Prepare data for CSV
    csv_data = []
    for chapter in all_chapters:
        for heading_number, heading_text in chapter['headings']:
            csv_data.append({
                'subject': chapter['subject'],
                'class': chapter['class'],
                'chapter_file': chapter['chapter_file'],
                'chapter_number': chapter['chapter_number'],
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
    
    print(f"Successfully populated {output_file} with {len(csv_data)} headings from {len(all_chapters)} chapters")
    print(f"\nChapters added:")
    for chapter in all_chapters:
        print(f"  - {chapter['subject']} {chapter['class']}: {chapter['chapter_file']} ({len(chapter['headings'])} headings)")

def main():
    """Main function to populate all chapters."""
    populate_all_chapters()

if __name__ == '__main__':
    main()
