import together
import os

# Set the API key from environment
together.api_key = os.getenv("TOGETHER_API_KEY") or "your-key"

def generate_questions(subject, topic):
    response = together.chat.completions.create(
        model="meta-llama/Llama-3-8b-chat-hf",
        messages=[
            {"role": "system", "content": "You are a helpful tutor."},
            {"role": "user", "content": f"Generate 5 Class 12 {subject} questions on '{topic}'."}
        ],
        max_tokens=300,
        temperature=0.7
    )
    return response.choices[0].message.content

print(generate_questions("Chemistry", "Haloalkanes"))
