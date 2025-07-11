import together
import os

# --- NEW: Import the Together client class ---
from together import Together

# --- NEW: Instantiate the client with your API key ---
# It will automatically pick up TOGETHER_API_KEY from environment variables
client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# No need for this line anymore: together.api_key = os.getenv("TOGETHER_API_KEY")

if client.api_key is None: # Changed from together.api_key to client.api_key
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
    # Using 'messages' format for chat completion
    messages = [
        {"role": "system", "content": f"You are an expert tutor for {subject} for {grade} grade students. Generate a challenging and well-structured practice problem. The problem should be suitable for students preparing for competitive exams like JEE. Ensure it adheres to the difficulty level and concepts typical for {grade} grade {subject}."},
        {"role": "user", "content": f"Generate a practice problem on the topic of \"{topic}\"." +
                                      (f"\nStrictly adhere to the following syllabus context:\n{syllabus_context}" if syllabus_context else "") +
                                      "\nPlease provide only the problem statement, without the solution or explanation."}
    ]

    try:
        # --- NEW: Use client.chat.completions.create ---
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1", # Or another suitable model from Together AI
            messages=messages, # Pass the messages list
            max_tokens=500, # Adjust as needed for problem length
            temperature=0.7 # Adjust for creativity vs. consistency
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating problem with Together AI: {e}")
        return "Could not generate problem at this time."

# Example Usage (for testing the script directly)
if __name__ == "__main__":
    print("AI Tutor Q&A Script")
    print("--------------------")
    # Example 1: Basic problem
    problem_physics = generate_practice_problem("Physics", "11th", "Newton's Laws of Motion")
    print("\n--- Physics Problem ---")
    print(problem_physics)

    # Example 2: Problem with syllabus context
    sample_syllabus = "States of matter: classification of solids, amorphous and crystalline solids; band theory of metals, conductors, semiconductors and insulators; p- and n- type semiconductors."
    problem_chemistry = generate_practice_problem("Chemistry", "12th", "Semiconductors", sample_syllabus)
    print("\n--- Chemistry Problem (with syllabus context) ---")
    print(problem_chemistry)