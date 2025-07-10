const TOGETHER_API_KEY = import.meta.env.VITE_TOGETHER_API_KEY;

export async function generateFromTogether(prompt) {
  const response = await fetch("https://api.together.xyz/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${TOGETHER_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: "meta-llama/Llama-3-8b-chat-hf",
      messages: [{ role: "user", content: prompt }],
      max_tokens: 1024,
      temperature: 0.7
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Together API error: ${error}`);
  }

  const data = await response.json();
  return data.choices[0].message.content;
}
