// src/ProblemGenerator.jsx

import React, { useState, useEffect } from 'react';
import axios from 'axios'; // Make sure you have axios installed: npm install axios
import { useLocation } from 'react-router-dom'; // Import useLocation from react-router-dom

export default function ProblemGenerator() {
  const [prompt, setPrompt] = useState('');
  const [generatedProblem, setGeneratedProblem] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [syllabusText, setSyllabusText] = useState(''); // State to store syllabus text

  const location = useLocation(); // Get location object from React Router
  // Access the passed syllabusId from the Link state.
  // This assumes you're passing it like: <Link to={{ pathname: "/generate-problem", state: { syllabusId: "YOUR_ID" } }}>
  const syllabusId = location.state?.syllabusId; 

  // --- useEffect to fetch syllabus text when component mounts or syllabusId changes ---
  useEffect(() => {
    const fetchSyllabusText = async () => {
      if (!syllabusId) {
        // console.log("No syllabus ID provided to ProblemGenerator.");
        return; // Don't fetch if no ID
      }
      setError('');
      try {
        // Make sure your FastAPI backend is running on http://127.0.0.1:8000
        const response = await axios.get(`http://127.0.0.1:8000/get-syllabus-text/${syllabusId}`);
        setSyllabusText(response.data.syllabus_text);
        // console.log("Fetched syllabus text:", response.data.syllabus_text.substring(0, 100) + "..."); // Log first 100 chars
      } catch (err) {
        console.error("Error fetching syllabus text:", err.response ? err.response.data : err.message);
        setError("Failed to load syllabus context. Please ensure the syllabus ID is valid and the backend is running.");
      }
    };

    fetchSyllabusText();
  }, [syllabusId]); // Re-run this effect if syllabusId changes

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setGeneratedProblem('');

    // Combine user prompt with syllabus text as context for the AI
    // The LLM will use this combined text to generate a relevant problem.
    const fullPrompt = syllabusText 
      ? `Based on the following syllabus content, generate a practice problem:\n\nSyllabus Content:\n"${syllabusText}"\n\nUser Request: ${prompt}`
      : `Generate a practice problem based on: ${prompt}`;

    try {
      // --- THIS IS WHERE YOU'LL INTEGRATE WITH YOUR ACTUAL AI/LLM API ---
      // This is a placeholder for your LLM call. You would typically send 'fullPrompt'
      // to your backend's LLM endpoint (e.g., a FastAPI endpoint that calls Google Gemini).
      
      // Example of a simulated API call (replace with your actual backend call)
      const simulatedResponse = await new Promise(resolve => setTimeout(() => {
        resolve({ data: { problem: `Simulated problem for: "${prompt}"\n\nContext used (first 50 chars): "${syllabusText.substring(0, 50)}..."` } });
      }, 2000));
      
      setGeneratedProblem(simulatedResponse.data.problem);

      // Example of how you might call your actual backend LLM endpoint:
      /*
      const actualLLMResponse = await axios.post('http://127.0.0.1:8000/generate-llm-problem', {
        prompt: fullPrompt
      });
      setGeneratedProblem(actualLLMResponse.data.generated_text);
      */

    } catch (err) {
      console.error("Error generating problem:", err.response ? err.response.data : err.message);
      setError("Failed to generate problem. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: 'auto', color: '#fff' }}>
      <h2>Generate Practice Problem</h2>
      {syllabusId && <p style={{ fontSize: '0.9em', color: '#ccc' }}>Using Syllabus ID: <strong>{syllabusId}</strong></p>}
      {syllabusText && <p style={{ fontSize: '0.8em', color: '#888' }}>Syllabus content loaded. (First 100 chars): {syllabusText.substring(0, 100)}...</p>}
      {!syllabusText && syllabusId && <p style={{ color: 'orange' }}>Loading syllabus content or content is empty for this ID...</p>}
      {!syllabusId && <p style={{ color: '#aaa' }}>No Syllabus ID provided. Problem will be generated without specific syllabus context.</p>}
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g., 'A difficult problem on thermodynamics from Chapter 3'"
          rows="5"
          style={{ width: '100%', padding: '10px', backgroundColor: '#333', color: '#fff', border: '1px solid #555', borderRadius: '5px' }}
          required
        ></textarea>
        <button
          type="submit"
          disabled={isLoading || !prompt}
          style={{ padding: '10px 20px', backgroundColor: '#28a745', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
        >
          {isLoading ? 'Generating...' : 'Generate Problem'}
        </button>
      </form>

      {error && <p style={{ color: 'red', marginTop: '15px' }}>{error}</p>}

      {generatedProblem && (
        <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#222', border: '1px solid #444', borderRadius: '5px' }}>
          <h3>Generated Problem:</h3>
          <p style={{ whiteSpace: 'pre-wrap', color: '#ddd' }}>{generatedProblem}</p>
        </div>
      )}
    </div>
  );
}