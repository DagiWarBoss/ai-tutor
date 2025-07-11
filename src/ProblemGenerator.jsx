// src/ProblemGenerator.jsx (simplified example)
import React, { useState } from 'react';
import axios from 'axios';

function ProblemGenerator() {
  const [subject, setSubject] = useState('');
  const [grade, setGrade] = useState('');
  const [topic, setTopic] = useState('');
  const [syllabusText, setSyllabusText] = useState('');
  const [problem, setProblem] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setProblem(''); // Clear previous problem
    setError('');   // Clear previous error

    try {
      const response = await axios.post('http://localhost:8000/generate_problem', {
        subject,
        grade,
        topic,
        syllabus_text: syllabusText,
      });
      setProblem(response.data.problem);
    } catch (err) {
      console.error('Error generating problem:', err);
      setError('Error: No response from server. Is the FastAPI backend running?');
      setProblem(''); // Clear problem on error
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container"> {/* Assuming you have a container as suggested for styling */}
      <h2>Generate Practice Problems</h2>
      <form onSubmit={handleSubmit}>
        {/* ... your form inputs ... */}
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

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <h3>Generated Problem:</h3>
      <div className="generated-problem-output" style={{ backgroundColor: '#f0f0f0', padding: '20px', borderRadius: '8px' }}>
        {/* ADD THIS INLINE STYLE TO THE DIV DISPLAYING THE PROBLEM TEXT */}
        <div className="generated-problem-text" style={{ color: 'black', fontSize: '1.1em', lineHeight: '1.6', textAlign: 'left' }}>
          {problem}
        </div>
      </div>
    </div>
  );
}

export default ProblemGenerator;