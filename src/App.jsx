// src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard";
import Quiz from "./Quiz";
import AuthPage from "./AuthPage";
import SyllabusUpload from "./SyllabusUpload";

// Create a functional component that uses useNavigate and renders the main app logic
function AppContent() {
  const navigate = useNavigate(); // Now useNavigate is called within the Router's context

  const handleLogout = () => {
    localStorage.removeItem('userToken'); // Example: clear user token
    localStorage.removeItem('user'); // Also clear the 'user' email if it's stored separately
    console.log("User logged out!");
    navigate('/auth'); // Redirect to login page
  };

  return (
    <div className="app-container">
      {/* Simple Navigation Bar */}
      <nav className="main-nav">
        <ul>
          <li><Link to="/">Dashboard</Link></li>
          <li><Link to="/generate-problem">Generate Problem</Link></li>
          <li><Link to="/quiz">Quiz</Link></li>
          <li><Link to="/syllabus-upload">Syllabus Upload</Link></li>
          {localStorage.getItem('user') ? (
            <li>
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
  );
}

function App() {
  return (
    <Router>
      <AppContent /> {/* Render the AppContent component inside the Router */}
    </Router>
  );
}

export default App;