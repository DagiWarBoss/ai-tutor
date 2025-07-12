// src/App.jsx

import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext.jsx'; // Corrected import
import ProtectedRoute from './ProtectedRoute.jsx';
import { auth } from './firebase'; // Import auth for signOut

// Import your components
import ProblemGenerator from "./ProblemGenerator.jsx";
import Dashboard from "./Dashboard.jsx";
import Quiz from "./Quiz.jsx";
import AuthPage from "./AuthPage.jsx";
import SyllabusUpload from "./SyllabusUpload.jsx";

// Define AppContent component here, outside of the main App function
function AppContent() {
  const navigate = useNavigate();
  const { currentUser, loading } = useAuth();
  // State to hold the last uploaded syllabus ID, to be passed to ProblemGenerator
  const [lastUploadedSyllabusId, setLastUploadedSyllabusId] = useState(null); 

  console.log("AppContent - currentUser:", currentUser);
  console.log("AppContent - loading:", loading);
  console.log("AppContent - lastUploadedSyllabusId:", lastUploadedSyllabusId); // For debugging

  const handleLogout = async () => {
    try {
      await auth.signOut();
      console.log("User logged out via Firebase!");
      navigate('/auth'); // Redirect to login page
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };

  // Render a loading state if authentication status is not yet known
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'white' }}>
        Loading application...
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Simple Navigation Bar */}
      <nav className="main-nav">
        <ul>
          <li><Link to="/">Dashboard</Link></li>
          {/* Link to Problem Generator, passing the last uploaded syllabus ID via state */}
          <li>
            <Link
              to={{
                pathname: "/generate-problem",
                state: { syllabusId: lastUploadedSyllabusId } 
              }}
            >
              Generate Problem
            </Link>
          </li>
          <li><Link to="/quiz">Quiz</Link></li>
          {/* Link to Syllabus Upload */}
          <li>
            <Link to="/syllabus-upload">Syllabus Upload</Link>
          </li>
          {currentUser ? ( 
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
        {/* AuthPage is NOT protected */}
        <Route path="/auth" element={<AuthPage />} />

        {/* Wrap protected routes with ProtectedRoute */}
        <Route path="/" element={<ProtectedRoute><Dashboard handleLogout={handleLogout} /></ProtectedRoute>} />
        <Route path="/generate-problem" element={<ProtectedRoute><ProblemGenerator /></ProtectedRoute>} />
        <Route path="/quiz" element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
        {/* Pass the setLastUploadedSyllabusId function to SyllabusUpload */}
        {/* So SyllabusUpload can update AppContent's state on successful upload */}
        <Route 
          path="/syllabus-upload" 
          element={
            <ProtectedRoute>
              <SyllabusUpload onUploadSuccess={setLastUploadedSyllabusId} />
            </ProtectedRoute>
          } 
        />
        {/* Add any other protected routes similarly */}
      </Routes>
    </div>
  );
}

// The main App component wraps everything with the Router and AuthProvider
function App() {
  return (
    <Router>
      <AuthProvider> {/* Wrap AppContent with AuthProvider */}
        <AppContent />
      </AuthProvider>
    </Router>
  );
}

export default App;