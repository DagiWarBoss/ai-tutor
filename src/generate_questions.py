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

def generate_practice_problem(subject: str, grade: str, topic: str, syllabus_context: str = ""):
    messages = [
        {"role": "system", "content": f"You are an expert tutor for {subject} for {grade} grade students. Generate a challenging and well-structured practice problem. The problem should be suitable for students preparing for competitive exams like JEE. Ensure it adheres to the difficulty level and concepts typical for {grade} grade {subject}."},
        {"role": "user", "content": f"Generate a practice problem on the topic of \"{topic}\"." +
                                     (f"\nStrictly adhere to the following syllabus context:\n{syllabus_context}" if syllabus_context else "") +
                                     "\nPlease provide only the problem statement, without the solution or explanation."}
    ]

    try:
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        # --- ADD THESE PRINT STATEMENTS ---
        print("\n--- Together AI API Response ---")
        print(f"Full API Response Object: {response}")
        generated_content = response.choices[0].message.content
        print(f"Extracted Generated Content: '{generated_content}'")
        print("------------------------------\n")
        # --- END ADDITIONS ---

        return generated_content
    except together.error.TogetherAuthenticationError:
        print("\nError: Authentication failed with Together AI. Please check your API key.")
        return "Authentication failed. Could not generate problem."
    except together.error.TogetherError as e:
        print(f"\nError from Together AI: {e}")
        return "Together AI error. Could not generate problem."
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return "Could not generate problem at this time."

if __name__ == "__main__":
    print("AI Tutor Q&A Script")
    print("--------------------")

    problem_physics = generate_practice_problem("Physics", "11th", "Newton's Laws of Motion")
    print("\n--- Physics Problem ---")
    print(problem_physics)

    sample_syllabus = "States of matter: classification of solids, amorphous and crystalline solids; band theory of metals, conductors, semiconductors and insulators; p- and n- type semiconductors."
    problem_chemistry = generate_practice_problem("Chemistry", "12th", "Semiconductors", sample_syllabus)
    print("\n--- Chemistry Problem (with syllabus context) ---")
    print(problem_chemistry)