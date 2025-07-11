# src/generate_questions.py
import together
import os
from together import Together

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

if TOGETHER_API_KEY is None:
    print("Error: TOGETHER_API_KEY environment variable not set.")
    print("Please set your Together AI API key before running the script.")
    print("For Windows, in Command Prompt: setx TOGETHER_API_KEY \"YOUR_ACTUAL_KEY\" (then open a NEW Command Prompt)")
    exit()

client = Together(api_key=TOGETHER_API_KEY)

def generate_problem_and_solution(subject: str, grade: str, topic: str, syllabus_context: str = ""):
    """
    Generates a practice problem AND its solution using Together AI.

    Args:
        subject (str): e.g., "Physics", "Chemistry", "Mathematics"
        grade (str): e.g., "11th", "12th"
        topic (str): Specific topic, e.g., "Kinematics", "Organic Chemistry", "Calculus"
        syllabus_context (str): Relevant text from the syllabus.

    Returns:
        tuple[str, str]: A tuple containing the generated problem string and solution string.
                        Returns error messages if generation fails.
    """
    # Prompt for the problem
    problem_messages = [
        {"role": "system", "content": f"You are an expert tutor for {subject} for {grade} grade students. Generate a challenging and well-structured practice problem. The problem should be suitable for students preparing for competitive exams like JEE. Ensure it adheres to the difficulty level and concepts typical for {grade} grade {subject}."},
        {"role": "user", "content": f"Generate a practice problem on the topic of \"{topic}\"." +
                                     (f"\nStrictly adhere to the following syllabus context:\n{syllabus_context}" if syllabus_context else "") +
                                     "\nPlease provide only the problem statement, without the solution or explanation."}
    ]

    try:
        problem_response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=problem_messages,
            max_tokens=500,
            temperature=0.7
        )
        problem_text = problem_response.choices[0].message.content
        print(f"Generated Problem (from AI): '{problem_text}'")

        # Prompt for the solution based on the generated problem
        solution_messages = [
            {"role": "system", "content": f"You are an expert tutor for {subject} for {grade} grade students. Provide a detailed, step-by-step solution for the following practice problem."},
            {"role": "user", "content": f"Problem: {problem_text}\n\nProvide the complete solution with detailed steps and the final answer."}
        ]

        solution_response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1", # Use the same or another suitable model
            messages=solution_messages,
            max_tokens=1000, # More tokens for a detailed solution
            temperature=0.5 # Lower temperature for less creativity, more factual solution
        )
        solution_text = solution_response.choices[0].message.content
        print(f"Generated Solution (from AI): '{solution_text}'")

        return problem_text, solution_text

    except together.error.TogetherAuthenticationError:
        print("\nError: Authentication failed with Together AI. Please check your API key.")
        return "Authentication failed. Could not generate problem.", "Authentication failed. Could not generate solution."
    except together.error.TogetherError as e:
        print(f"\nError from Together AI: {e}")
        return "Together AI error. Could not generate problem.", "Together AI error. Could not generate solution."
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return "Could not generate problem at this time.", "Could not generate solution at this time."

# Example Usage (for testing the script directly)
if __name__ == "__main__":
    print("AI Tutor Q&A Script")
    print("--------------------")

    problem_physics, solution_physics = generate_problem_and_solution("Physics", "11th", "Newton's Laws of Motion")
    print("\n--- Physics Problem ---")
    print(problem_physics)
    print("\n--- Physics Solution ---")
    print(solution_physics)