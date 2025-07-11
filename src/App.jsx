// src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard"; // Assuming Dashboard.jsx is directly in src/
import Quiz from "./Quiz";           // Assuming Quiz.jsx is directly in src/
import AuthPage from "./AuthPage";   // Assuming AuthPage.jsx is directly in src/
import SyllabusUpload from "./SyllabusUpload"; // Assuming SyllabusUpload.jsx is directly in src/

// You can remove TestAI import and usage as it was confirmed not to exist
// import TestAI from "./TestAI"; 

function App() {
  return (
    <Router> {/* Wrap your entire app with Router */}
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
            <li>
              <Link to="/auth">Auth Page</Link>
            </li>
          </ul>
        </nav>

        {/* Horizontal rule for separation, adjust as needed */}
        <hr style={{ margin: '30px 0', borderColor: '#555' }} />

        {/* Define your routes */}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/generate-problem" element={<ProblemGenerator />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/syllabus-upload" element={<SyllabusUpload />} />
          {/* Add more routes here for other components like SubjectDetail, etc. */}
          {/* Example for a dynamic quiz route, if you need it: */}
          {/* <Route path="/quiz/:subject" element={<Quiz />} /> */}
        </Routes>
      </div>
    </Router>
  );
}

export default App;