// src/ProblemGenerator.jsx

import React, { useState } from 'react';
import axios from 'axios'; // Ensure axios is installed (npm install axios)

function ProblemGenerator() {
  // State variables for form inputs and generated problem/error
  const [subject, setSubject] = useState('');
  const [grade, setGrade] = useState('');
  const [topic, setTopic] = useState('');
  const [syllabusText, setSyllabusText] = useState('');
  const [problem, setProblem] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Handler for form submission
  const handleSubmit = async (e) => {
    e.preventDefault(); // Prevent default form submission behavior (page reload)
    setLoading(true);   // Set loading state to true
    setProblem('');     // Clear any previous problem
    setError('');       // Clear any previous error message

    try {
      // Send a POST request to your FastAPI backend
      const response = await axios.post('http://localhost:8000/generate_problem', {
        subject,
        grade,
        topic,
        syllabus_text: syllabusText,
      });
      // Set the problem with the response data
      setProblem(response.data.problem);
    } catch (err) {
      // Log the full error object for debugging
      console.error('Error generating problem:', err);

      // Set user-friendly error message
      if (err.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        setError(`Server error: ${err.response.status} - ${err.response.data.detail || 'Unknown error'}`);
      } else if (err.request) {
        // The request was made but no response was received
        setError('Error: No response from server. Is the FastAPI backend running?');
      } else {
        // Something else happened while setting up the request
        setError(`An unexpected error occurred: ${err.message}`);
      }
      setProblem(''); // Ensure problem area is clear on error
    } finally {
      setLoading(false); // Reset loading state
    }
  };

  return (
    <div className="container"> {/* Main container div for styling */}
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

      {/* Display error messages if any */}
      {error && <p style={{ color: 'red', marginTop: '20px' }}>{error}</p>}

      <h3>Generated Problem:</h3>
      {/* Container for the generated problem output */}
      <div className="generated-problem-output">
        {/* Div to display the problem text. Styles will come from App.css */}
        <div className="generated-problem-text">
          {problem}
        </div>
      </div>
    </div>
  );
}

export default ProblemGenerator;