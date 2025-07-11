// src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom'; // Import useNavigate

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard";
import Quiz from "./Quiz";
import AuthPage from "./AuthPage";
import SyllabusUpload from "./SyllabusUpload";

function App() {
  const navigate = useNavigate(); // Initialize useNavigate hook

  const handleLogout = () => {
    // Implement your actual logout logic here
    // For example, if you're using localStorage to store a token:
    localStorage.removeItem('userToken'); // Or whatever key your token is stored under
    console.log("User logged out!");

    // Redirect to the login page or home page after logout
    navigate('/auth'); // Assuming '/auth' is your login page
    // Or navigate('/') if you want to go to the dashboard/home page
  };

  return (
    <Router>
      <div className="app-container">
        {/* Simple Navigation Bar */}
        <nav className="main-nav">
          <ul>
            <li>
              <Link to="/">Dashboard</Link>
            </li>
            <li>
              <Link to="/generate-problem">Generate Problem</Link>
            </li>
            <li>
              <Link to="/quiz">Quiz</Link>
            </li>
            <li>
              <Link to="/syllabus-upload">Syllabus Upload</Link>
            </li>
            {/* You might conditionally render Auth/Logout based on login status */}
            {localStorage.getItem('userToken') ? ( // Example: show logout if token exists
              <li>
                <button onClick={handleLogout} className="nav-button">Logout</button>
              </li>
            ) : (
              <li>
                <Link to="/auth">Login / Register</Link>
              </li>
            )}
          </ul>
        </nav>

        {/* Horizontal rule for separation */}
        <hr style={{ margin: '30px 0', borderColor: '#555' }} />

        {/* Define your routes */}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/generate-problem" element={<ProblemGenerator />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/syllabus-upload" element={<SyllabusUpload />} />
          {/* Add more routes here for other components like SubjectDetail, etc. */}
        </Routes>
      </div>
    </Router>
  );
}

export default App;