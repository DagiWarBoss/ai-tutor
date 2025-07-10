// src/components/TestAI.jsx
import { useState } from "react";
import { generateFromTogether } from "../utils/generateFromTogether";

export default function TestAI() {
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");

  const handleClick = async () => {
    try {
      const res = await generateFromTogether(prompt);
      setResponse(res);
    } catch (err) {
      setResponse("Error: " + err.message);
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Ask AI (Together API)</h2>
      <input
        style={{ width: "300px", padding: "8px", marginRight: "10px" }}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Type a question..."
      />
      <button onClick={handleClick} style={{ padding: "8px 16px" }}>
        Send
      </button>
      <div style={{ marginTop: "20px", whiteSpace: "pre-wrap" }}>
        <strong>Response:</strong>
        <p>{response}</p>
      </div>
    </div>
  );
}
