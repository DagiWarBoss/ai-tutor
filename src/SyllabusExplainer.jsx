import React, { useState } from 'react';

// A simple book icon for the button
const BookOpenIcon = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
  </svg>
);

export default function SyllabusExplainer() {
  // We'll now use a natural language question for the input
  const [question, setQuestion] = useState('why does a ball fall down?');
  const [answer, setAnswer] = useState('');
  const [sourceChapter, setSourceChapter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question) {
      setError('Please enter a question.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setAnswer('');
    setSourceChapter('');

    try {
      // THIS IS THE FIX: We are now calling the correct '/ask-question' endpoint
      const response = await fetch('http://localhost:8000/ask-question', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // The body now sends a 'question' instead of a 'chapter_name'
        body: JSON.stringify({ question: question }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnswer(data.answer);
      setSourceChapter(data.source_chapter);

    } catch (err) {
      console.error("Failed to get answer:", err);
      setError(`Failed to get answer from the AI Tutor. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-4 font-sans">
      <div className="w-full max-w-3xl">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-cyan-400">AI Syllabus Explainer (Smart Test)</h1>
          <p className="text-gray-400 mt-2">Ask any question, and the AI will find the relevant chapter to answer it.</p>
        </header>

        <form onSubmit={handleSubmit} className="w-full mb-8">
          <div className="flex flex-col sm:flex-row gap-4">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g., why is the sky blue? or explain newton's laws"
              className="flex-grow bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition duration-200"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center justify-center bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-900 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg transition duration-200 shadow-lg shadow-cyan-600/20"
            >
              <BookOpenIcon className="w-5 h-5 mr-2" />
              {isLoading ? 'Thinking...' : 'Ask Question'}
            </button>
          </div>
        </form>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 min-h-[300px] flex items-center justify-center">
          {isLoading && (
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
              <p className="mt-4 text-gray-400">Searching knowledge base and generating answer...</p>
            </div>
          )}

          {error && (
            <div className="text-red-400 bg-red-900/20 border border-red-700 rounded-lg p-4">
              <h3 className="font-bold mb-2">An Error Occurred</h3>
              <p>{error}</p>
            </div>
          )}

          {answer && (
            <div className="text-left w-full">
              {sourceChapter && (
                <p className="text-sm text-gray-500 mb-4 border-b border-gray-700 pb-2">
                  <span className="font-bold">Source Chapter:</span> {sourceChapter}
                </p>
              )}
              <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">{answer}</p>
            </div>
          )}

          {!isLoading && !error && !answer && (
            <p className="text-gray-500">The AI-generated answer will appear here.</p>
          )}
        </div>
         <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>AI Tutor Alpha v0.3 - Semantic Search RAG Pipeline</p>
        </footer>
      </div>
    </div>
  );
}
