// src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard";
import Quiz from "./Quiz";
import AuthPage from "./AuthPage";
import SyllabusUpload from "./SyllabusUpload";

function App() {
  const navigate = useNavigate();

  const handleLogout = () => {
    // Implement your actual logout logic here
    localStorage.removeItem('userToken'); // Example: clear user token
    localStorage.removeItem('user'); // Also clear the 'user' email if it's stored separately
    console.log("User logged out!");
    navigate('/auth'); // Redirect to login page
  };

  return (
    <Router>
      <div className="app-container">
        {/* Navigation */}
        <nav className="main-nav">
          <ul>
            <li><Link to="/">Dashboard</Link></li>
            <li><Link to="/generate-problem">Generate Problem</Link></li>
            <li><Link to="/quiz">Quiz</Link></li>
            <li><Link to="/syllabus-upload">Syllabus Upload</Link></li>
            {localStorage.getItem('user') ? ( // Check for 'user' email for display logic
              <li>
                {/* Use a button for logout as it performs an action, not navigation */}
                <button onClick={handleLogout} className="nav-button">Logout</button>
              </li>
            ) : (
              <li><Link to="/auth">Login / Register</Link></li>
            )}
          </ul>
        </nav>

        <hr style={{ margin: '30px 0', borderColor: '#555' }} />

        {/* Define your routes */}
        <Routes>
          {/* Pass handleLogout function as a prop to Dashboard */}
          <Route path="/" element={<Dashboard handleLogout={handleLogout} />} />
          <Route path="/generate-problem" element={<ProblemGenerator />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/syllabus-upload" element={<SyllabusUpload />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;