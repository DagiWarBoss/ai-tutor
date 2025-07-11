import together
import os

# Set your Together AI API Key from environment variables
together.api_key = os.getenv("TOGETHER_API_KEY")

if together.api_key is None:
    print("Error: TOGETHER_API_KEY environment variable not set.")
    print("Please set your Together AI API key.")
    exit()

def generate_practice_problem(subject: str, grade: str, topic: str, syllabus_context: str = ""):
    """
    Generates a practice problem using Together AI.

    Args:
        subject (str): e.g., "Physics", "Chemistry", "Mathematics"
        grade (str): e.g., "11th", "12th"
        topic (str): Specific topic, e.g., "Kinematics", "Organic Chemistry", "Calculus"
        syllabus_context (str): Relevant text from the syllabus.

    Returns:
        str: The generated practice problem.
    """
    # Crafting the prompt is crucial for good results
    prompt = f"""You are an expert tutor for {subject} for {grade} grade students.
    Generate a challenging and well-structured practice problem on the topic of "{topic}".
    The problem should be suitable for students preparing for competitive exams like JEE.
    Ensure it adheres to the difficulty level and concepts typical for {grade} grade {subject}.

    If syllabus context is provided, strictly adhere to the concepts mentioned in it.

    Syllabus Context:
    {syllabus_context if syllabus_context else "None provided."}

    Please provide only the problem statement, without the solution or explanation."""

    try:
        # Using the chat completions endpoint for better control over persona and instructions
        response = together.completion.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1", # Or another suitable model from Together AI
            prompt=prompt,
            max_tokens=500, # Adjust as needed for problem length
            temperature=0.7 # Adjust for creativity vs. consistency
        )
        return response['choices'][0]['text']
    except Exception as e:
        print(f"Error generating problem with Together AI: {e}")
        return "Could not generate problem at this time."

# Example Usage (for testing the script directly)
if __name__ == "__main__":
    # Make sure TOGETHER_API_KEY is set in your environment
    # Example 1: Basic problem
    problem_physics = generate_practice_problem("Physics", "11th", "Newton's Laws of Motion")
    print("\n--- Physics Problem ---")
    print(problem_physics)

    # Example 2: Problem with syllabus context
    sample_syllabus = "States of matter: classification of solids, amorphous and crystalline solids; band theory of metals, conductors, semiconductors and insulators; p- and n- type semiconductors."
    problem_chemistry = generate_practice_problem("Chemistry", "12th", "Semiconductors", sample_syllabus)
    print("\n--- Chemistry Problem (with syllabus context) ---")
    print(problem_chemistry)