import together
import os
from together import Together # Keep this import

# --- IMPORTANT FIX FOR API KEY HANDLING ---

# 1. Get the API key from the environment variable first
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

# 2. Check if the API key was actually retrieved
if TOGETHER_API_KEY is None:
    print("Error: TOGETHER_API_KEY environment variable not set.")
    print("Please set your Together AI API key before running the script.")
    print("For Windows, in Command Prompt: setx TOGETHER_API_KEY \"YOUR_ACTUAL_KEY\" (then open a NEW Command Prompt)")
    exit() # Exit the script if the key is not found

# 3. If the key is found, then safely instantiate the Together client
client = Together(api_key=TOGETHER_API_KEY)

# --- End of API Key Handling Fix ---


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
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1", # Or another suitable model from Together AI
            messages=messages, # Pass the messages list
            max_tokens=500, # Adjust as needed for problem length
            temperature=0.7 # Adjust for creativity vs. consistency
        )
        return response.choices[0].message.content
    # It's good practice to catch specific API errors from the 'together' library
    except together.error.TogetherAuthenticationError:
        print("\nError: Authentication failed with Together AI. Please check your API key.")
        return "Authentication failed. Could not generate problem."
    except together.error.TogetherError as e: # Catch other Together AI specific errors
        print(f"\nError from Together AI: {e}")
        return "Together AI error. Could not generate problem."
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
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