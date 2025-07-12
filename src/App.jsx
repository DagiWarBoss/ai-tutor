// src/App.jsx

import React, { useState } from 'react'; // Added useState for dynamic syllabusId
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext.jsx'; // Corrected to .jsx
import ProtectedRoute from './ProtectedRoute.jsx'; // Corrected to .jsx
import { auth } from './firebase'; // Import auth for signOut

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard";
import Quiz from "./Quiz";
import AuthPage from "./AuthPage";
import SyllabusUpload from "./SyllabusUpload.jsx"; // Corrected to .jsx

// Define AppContent component here, outside of the main App function
function AppContent() {
  const navigate = useNavigate();
  const { currentUser, loading } = useAuth(); // Use the auth context here
  const [lastUploadedSyllabusId, setLastUploadedSyllabusId] = useState(null); // State to hold the last uploaded syllabus ID

  // Console logs for debugging authentication state - keep them for now
  console.log("AppContent - currentUser:", currentUser);
  console.log("AppContent - loading:", loading);

  const handleLogout = async () => {
    try {
      await auth.signOut(); // Use Firebase signOut from firebase.js
      console.log("User logged out via Firebase!");
      navigate('/auth'); // Redirect to login page
    } catch (error) {
      console.error("Error logging out:", error);
      // Handle error, e.g., display a message
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
          {/* Link to Problem Generator, passing the last uploaded syllabus ID */}
          <li>
            <Link
              to={{
                pathname: "/generate-problem",
                state: { syllabusId: lastUploadedSyllabusId } // Pass the dynamic ID here
              }}
            >
              Generate Problem
            </Link>
          </li>
          <li><Link to="/quiz">Quiz</Link></li>
          {/* Syllabus Upload link. We'll need a way to update lastUploadedSyllabusId from SyllabusUpload component */}
          <li>
            <Link to="/syllabus-upload">Syllabus Upload</Link>
          </li>
          {currentUser ? ( // Use currentUser from AuthContext for conditional rendering
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
        {/* Pass a function to SyllabusUpload to update the lastUploadedSyllabusId in AppContent */}
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