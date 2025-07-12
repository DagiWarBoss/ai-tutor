// frontend/src/ProblemGenerator.jsx

import React, { useState, useContext, useEffect } from 'react';
import axios from 'axios';
import { AuthContext } from "./AuthContext"; // Corrected path
import { AppContentContext } from "./AppContentContext"; // Corrected path
import "./index.css"; // Make sure this path is correct if you have global styles

const ProblemGenerator = () => {
    const { currentUser } = useContext(AuthContext);
    // Access lastUploadedSyllabusId from AppContentContext
    const { lastUploadedSyllabusId } = useContext(AppContentContext); 
    const [prompt, setPrompt] = useState('');
    const [generatedProblem, setGeneratedProblem] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleGenerateProblem = async () => {
        setLoading(true);
        setGeneratedProblem('');
        setError('');

        try {
            const requestBody = {
                prompt: prompt,
                // Pass syllabusId as a separate field if available
                syllabusId: lastUploadedSyllabusId || null // Send null if no ID
            };

            const response = await axios.post(
                'http://127.0.0.1:8000/generate-llm-problem',
                requestBody,
                {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                }
            );

            setGeneratedProblem(response.data.generated_text);
        } catch (err) {
            console.error('Error generating problem:', err);
            setError(err.response?.data?.detail || 'Failed to generate problem. Please try again. Check backend logs for details.');
            setGeneratedProblem(''); // Clear any previous partial generation
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container mx-auto p-4 max-w-2xl bg-white rounded-lg shadow-md mt-10">
            <h1 className="text-3xl font-bold mb-6 text-gray-800 text-center">Generate Practice Problem</h1>
            
            {/* Display message about syllabus context */}
            {lastUploadedSyllabusId ? (
                <p className="text-green-600 mb-4 text-center">
                    Using syllabus ID: {lastUploadedSyllabusId}. Problem will be generated with context.
                </p>
            ) : (
                <p className="text-red-500 mb-4 text-center">
                    No Syllabus ID provided. Problem will be generated without specific syllabus context.
                </p>
            )}

            <div className="mb-4">
                <label htmlFor="prompt" className="block text-gray-700 text-sm font-bold mb-2">
                    Enter your problem prompt (e.g., "a difficult question on quantum physics", "a multiple choice problem about Newton's laws"):
                </label>
                <textarea
                    id="prompt"
                    className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline resize-y"
                    rows="4"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="E.g., Generate a multiple choice question about the Doppler effect."
                ></textarea>
            </div>

            <button
                onClick={handleGenerateProblem}
                className={`w-full py-2 px-4 rounded focus:outline-none focus:shadow-outline transition duration-200 
                    ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-500 hover:bg-green-700 text-white font-bold'}`}
                disabled={loading}
            >
                {loading ? 'Generating...' : 'Generate Problem'}
            </button>

            {error && <p className="text-red-500 mt-4 text-center">{error}</p>}

            {generatedProblem && (
                <div className="mt-6 p-4 bg-gray-100 rounded border border-gray-300">
                    <h2 className="text-xl font-semibold mb-2 text-gray-800">Generated Problem:</h2>
                    <p className="text-gray-700 whitespace-pre-wrap">{generatedProblem}</p>
                </div>
            )}
        </div>
    );
};

export default ProblemGenerator;