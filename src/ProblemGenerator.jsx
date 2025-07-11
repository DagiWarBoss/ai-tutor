// src/ProblemGenerator.jsx
import React, { useState } from 'react';
import axios from 'axios'; // Make sure you have axios installed: npm install axios in your frontend project

function ProblemGenerator() {
    const [subject, setSubject] = useState('Physics');
    const [grade, setGrade] = useState('11th');
    const [topic, setTopic] = useState('');
    const [syllabusText, setSyllabusText] = useState('');
    const [generatedProblem, setGeneratedProblem] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setGeneratedProblem('');

        try {
            const response = await axios.post('http://localhost:8000/generate_problem', {
                subject: subject,
                grade: grade,
                topic: topic,
                syllabus_text: syllabusText // Send the syllabus text, even if empty
            });
            setGeneratedProblem(response.data.problem);
        } catch (err) {
            console.error("Error generating problem:", err);
            if (err.response) {
                // If the server responded with an error (e.g., HTTP 500 from FastAPI)
                setError(`Error from server: ${err.response.data.detail || 'Unknown error'}`);
            } else if (err.request) {
                // The request was made but no response was received (e.g., network error, CORS)
                setError("No response from server. Is the FastAPI backend running?");
            } else {
                // Something else happened in setting up the request
                setError("An unexpected error occurred while making the request.");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
            <h1>Generate Practice Problems</h1>
            <form onSubmit={handleSubmit}>
                <div>
                    <label>Subject:</label>
                    <select value={subject} onChange={(e) => setSubject(e.target.value)} disabled={loading}>
                        <option value="Physics">Physics</option>
                        <option value="Chemistry">Chemistry</option>
                        <option value="Mathematics">Mathematics</option>
                    </select>
                </div>
                <div style={{ marginTop: '10px' }}>
                    <label>Grade:</label>
                    <select value={grade} onChange={(e) => setGrade(e.target.value)} disabled={loading}>
                        <option value="11th">11th Grade</option>
                        <option value="12th">12th Grade</option>
                    </select>
                </div>
                <div style={{ marginTop: '10px' }}>
                    <label>Topic (e.g., "Kinematics", "Electrochemistry"):</label>
                    <input
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder="Enter specific topic"
                        required
                        disabled={loading}
                        style={{ width: '300px', padding: '5px' }}
                    />
                </div>
                <div style={{ marginTop: '10px' }}>
                    <label>Syllabus Context (Optional, for better relevance):</label>
                    <textarea
                        value={syllabusText}
                        onChange={(e) => setSyllabusText(e.target.value)}
                        placeholder="Paste relevant syllabus text here (e.g., from your extracted PDFs)"
                        rows="5"
                        cols="50"
                        disabled={loading}
                        style={{ display: 'block', marginTop: '5px' }}
                    />
                </div>
                <button type="submit" disabled={loading} style={{ marginTop: '15px', padding: '10px 20px' }}>
                    {loading ? 'Generating...' : 'Generate Problem'}
                </button>
            </form>

            {error && <p style={{ color: 'red', marginTop: '20px' }}>Error: {error}</p>}

            {generatedProblem && (
                <div style={{ marginTop: '30px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
                    <h2>Generated Problem:</h2>
                    <pre style={{ whiteSpace: 'pre-wrap', backgroundColor: '#f0f0f0', padding: '15px', borderRadius: '5px' }}>
                        {generatedProblem}
                    </pre>
                </div>
            )}
        </div>
    );
}

export default ProblemGenerator;