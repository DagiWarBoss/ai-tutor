import React, { useState } from 'react';
// 1. Import the KaTeX component and its CSS
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';


// Icons for UI elements
const SparklesIcon = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.9 5.8-5.8 1.9 5.8 1.9L12 21l1.9-5.8 5.8-1.9-5.8-1.9L12 3z" /><path d="M5 3v4" /><path d="M19 17v4" /><path d="M3 5h4" /><path d="M17 19h4" /></svg>
);

const ChevronDownIcon = ({ className }) => (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
);

// 2. Create a component to render text with math
const MathText = ({ text }) => {
    // This regex splits the text by LaTeX delimiters ($...$ and $$...$$)
    const parts = text.split(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);

    return (
        <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
            {parts.map((part, index) => {
                if (part.startsWith('$$') && part.endsWith('$$')) {
                    // Display math for block-level equations
                    return <BlockMath key={index} math={part.slice(2, -2)} />;
                } else if (part.startsWith('$') && part.endsWith('$')) {
                    // Display math for inline equations
                    return <InlineMath key={index} math={part.slice(1, -1)} />;
                }
                // Render regular text
                return <span key={index}>{part}</span>;
            })}
        </p>
    );
};


export default function ProblemGenerator() {
  const [topic, setTopic] = useState('Thermodynamics');
  const [generatedProblem, setGeneratedProblem] = useState('');
  const [solution, setSolution] = useState('');
  const [sourceChapter, setSourceChapter] = useState('');
  const [showSolution, setShowSolution] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!topic) {
      setError('Please enter a topic.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setGeneratedProblem('');
    setSolution('');
    setSourceChapter('');
    setShowSolution(false);

    try {
      const response = await fetch('http://localhost:8000/generate-grounded-problem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setGeneratedProblem(data.problem);
      setSolution(data.solution);
      setSourceChapter(data.source_chapter);

    } catch (err) {
      console.error("Failed to generate problem:", err);
      setError(`Failed to generate problem. Make sure the topic is clear and the backend is running. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-4 font-sans">
      <div className="w-full max-w-3xl">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-purple-400">Grounded Problem Generator</h1>
          <p className="text-gray-400 mt-2">Enter a topic to generate a JEE (Mains & Advanced) problem based on the NCERT syllabus.</p>
        </header>

        <form onSubmit={handleSubmit} className="w-full mb-8">
          <div className="flex flex-col sm:flex-row gap-4">
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
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

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 min-h-[300px] flex flex-col items-center justify-center">
          {isLoading && ( /* ... loading spinner ... */ )}
          {error && ( /* ... error message ... */ )}

          {generatedProblem && (
            <div className="text-left w-full">
              {sourceChapter && (
                <p className="text-sm text-gray-500 mb-4 border-b border-gray-700 pb-2">
                  <span className="font-bold">Source Chapter:</span> {sourceChapter}
                </p>
              )}
              <h2 className="text-xl font-semibold mb-4 text-purple-300">Generated Problem:</h2>
              {/* 3. Use the new MathText component */}
              <MathText text={generatedProblem} />
              
              <div className="mt-6">
                <button 
                  onClick={() => setShowSolution(!showSolution)}
                  className="flex items-center justify-between w-full text-left bg-gray-700 hover:bg-gray-600 px-4 py-3 rounded-lg focus:outline-none transition-colors duration-200"
                >
                  <span className="font-semibold text-purple-300">{showSolution ? 'Hide' : 'Show'} Solution</span>
                  <ChevronDownIcon className={`w-5 h-5 text-purple-300 transition-transform duration-300 ${showSolution ? 'rotate-180' : ''}`} />
                </button>
                {showSolution && solution && (
                  <div className="mt-2 p-4 bg-gray-900/50 rounded-b-lg border-t-0 border border-gray-700">
                    {/* 3. Use the new MathText component for the solution too */}
                    <MathText text={solution} />
                  </div>
                )}
              </div>
            </div>
          )}

          {!isLoading && !error && !generatedProblem && (
            <p className="text-gray-500">The generated problem will appear here.</p>
          )}
        </div>
         <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>AI Tutor Alpha v0.5 - Math Rendering Enabled</p>
        </footer>
      </div>
    </div>
  );
}
