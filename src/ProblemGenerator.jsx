import React, { useState } from 'react';

// This is a simple icon component for the button. You can replace it with any library like lucide-react.
const SparklesIcon = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m12 3-1.9 5.8-5.8 1.9 5.8 1.9L12 21l1.9-5.8 5.8-1.9-5.8-1.9L12 3z" />
    <path d="M5 3v4" />
    <path d="M19 17v4" />
    <path d="M3 5h4" />
    <path d="M17 19h4" />
  </svg>
);

// This is the component for your ProblemGenerator.jsx file
export default function ProblemGenerator() {
  const [prompt, setPrompt] = useState('Thermodynamics'); // Default prompt for ease of testing
  const [generatedProblem, setGeneratedProblem] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt) {
      setError('Please enter a topic.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setGeneratedProblem('');

    try {
      // The backend server is running on http://localhost:8000
      const response = await fetch('http://localhost:8000/generate-llm-problem', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: prompt }),
      });

      if (!response.ok) {
        // Try to get a detailed error message from the backend
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setGeneratedProblem(data.generated_text);

    } catch (err) {
      console.error("Failed to generate problem:", err);
      setError(`Failed to connect to the AI service. Make sure your backend server is running. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-4 font-sans">
      <div className="w-full max-w-2xl">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-purple-400">JEE AI Tutor</h1>
          <p className="text-gray-400 mt-2">Enter a topic to generate a JEE (Mains & Advanced) level practice problem.</p>
        </header>

        <form onSubmit={handleSubmit} className="w-full mb-8">
          <div className="flex flex-col sm:flex-row gap-4">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Kinematics, Organic Chemistry..."
              className="flex-grow bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition duration-200"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center justify-center bg-purple-600 hover:bg-purple-700 disabled:bg-purple-900 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg transition duration-200 shadow-lg shadow-purple-600/20"
            >
              <SparklesIcon className="w-5 h-5 mr-2" />
              {isLoading ? 'Generating...' : 'Generate Problem'}
            </button>
          </div>
        </form>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 min-h-[200px] flex items-center justify-center">
          {isLoading && (
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400"></div>
              <p className="mt-4 text-gray-400">Contacting the AI model...</p>
            </div>
          )}

          {error && (
            <div className="text-red-400 bg-red-900/20 border border-red-700 rounded-lg p-4">
              <h3 className="font-bold mb-2">An Error Occurred</h3>
              <p>{error}</p>
            </div>
          )}

          {generatedProblem && (
            <div className="text-left w-full">
              <h2 className="text-xl font-semibold mb-4 text-purple-300">Generated Problem:</h2>
              <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">{generatedProblem}</p>
            </div>
          )}

          {!isLoading && !error && !generatedProblem && (
            <p className="text-gray-500">The generated problem will appear here.</p>
          )}
        </div>
         <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>AI Tutor Alpha v0.1</p>
        </footer>
      </div>
    </div>
  );
}
