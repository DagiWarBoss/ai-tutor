// src/ProblemGenerator.jsx

import React, { useState } from 'react';
import axios from 'axios';

function ProblemGenerator() {
  const [subject, setSubject] = useState('');
  const [grade, setGrade] = useState('');
  const [topic, setTopic] = useState('');
  const [syllabusText, setSyllabusText] = useState('');
  const [problem, setProblem] = useState('');
  const [solution, setSolution] = useState(''); // New state for solution
  const [showSolutionPopup, setShowSolutionPopup] = useState(false); // State for popup visibility
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setProblem('');
    setSolution(''); // Clear previous solution
    setError('');
    setShowSolutionPopup(false); // Hide popup on new generation

    try {
      const response = await axios.post('http://localhost:8000/generate_problem', {
        subject,
        grade,
        topic,
        syllabus_text: syllabusText,
      });
      setProblem(response.data.problem);
      setSolution(response.data.solution); // Set the solution from response
    } catch (err) {
      console.error('Error generating problem:', err);
      if (err.response) {
        setError(`Server error: ${err.response.status} - ${err.response.data.detail || 'Unknown error'}`);
      } else if (err.request) {
        setError('Error: No response from server. Is the FastAPI backend running?');
      } else {
        setError(`An unexpected error occurred: ${err.message}`);
      }
      setProblem('');
      setSolution('');
    } finally {
      setLoading(false);
    }
  };

  const handleShowSolution = () => {
    setShowSolutionPopup(true);
  };

  const handleCloseSolution = () => {
    setShowSolutionPopup(false);
  };

  return (
    <div className="container">
      <h2>Generate Practice Problems</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="subject">Subject:</label>
          <select id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} required>
            <option value="">Select Subject</option>
            <option value="Physics">Physics</option>
            <option value="Chemistry">Chemistry</option>
            <option value="Mathematics">Mathematics</option>
          </select>
        </div>
        <div>
          <label htmlFor="grade">Grade:</label>
          <select id="grade" value={grade} onChange={(e) => setGrade(e.target.value)} required>
            <option value="">Select Grade</option>
            <option value="11th">11th Grade</option>
            <option value="12th">12th Grade</option>
          </select>
        </div>
        <div>
          <label htmlFor="topic">Topic (e.g. "Kinematics", "Electrochemistry"):</label>
          <input
            type="text"
            id="topic"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            required
            placeholder="Enter a specific topic"
          />
        </div>
        <div>
          <label htmlFor="syllabus_text">Syllabus Context (Optional, for better relevance):</label>
          <textarea
            id="syllabus_text"
            value={syllabusText}
            onChange={(e) => setSyllabusText(e.target.value)}
            rows="5"
            placeholder="Paste relevant syllabus text here (e.g., from your extracted PDFs)"
          ></textarea>
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Generating...' : 'Generate Problem'}
        </button>
      </form>

      {error && <p style={{ color: 'red', marginTop: '20px' }}>{error}</p>}

      <h3>Generated Problem:</h3>
      <div className="generated-problem-output">
        <div className="generated-problem-text">
          {problem}
        </div>
      </div>

      {problem && ( // Only show the solution button if a problem exists
        <button onClick={handleShowSolution} style={{ marginTop: '15px' }}>
          Show Solution
        </button>
      )}

      {/* Solution Popup Modal */}
      {showSolutionPopup && (
        <div className="modal-overlay">
          <div className="modal-content">
            <button className="close-button" onClick={handleCloseSolution}>&times;</button>
            <h4>Solution:</h4>
            <div className="solution-text">
              {solution}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProblemGenerator;