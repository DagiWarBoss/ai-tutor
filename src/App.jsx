// src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext'; // Import AuthProvider and useAuth
import ProtectedRoute from './ProtectedRoute'; // Import ProtectedRoute

// Import your components
import ProblemGenerator from "./ProblemGenerator";
import Dashboard from "./Dashboard";
import Quiz from "./Quiz";
import AuthPage from "./AuthPage";
import SyllabusUpload from "./SyllabusUpload";

// This component now needs access to AuthContext
function AppContent() {
  const navigate = useNavigate();
  const { currentUser, loading } = useAuth(); // Use the auth context here

  const handleLogout = async () => { // Make it async because Firebase signOut is async
    try {
      await auth.signOut(); // Use Firebase signOut
      console.log("User logged out via Firebase!");
      // localStorage is updated by AuthContext listener, so no need to removeItem here.
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
          <li><Link to="/generate-problem">Generate Problem</Link></li>
          <li><Link to="/quiz">Quiz</Link></li>
          <li><Link to="/syllabus-upload">Syllabus Upload</Link></li>
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
        <Route path="/syllabus-upload" element={<ProtectedRoute><SyllabusUpload /></ProtectedRoute>} />
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
// src/App.jsx (inside AppContent function)
// ...
function AppContent() {
  const navigate = useNavigate();
  const { currentUser, loading } = useAuth(); // Use the auth context here

  console.log("AppContent - currentUser:", currentUser);
  console.log("AppContent - loading:", loading);

  const handleLogout = async () => {
    // ...
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'white' }}>
        Loading application...
      </div>
    );
  }
  // ... rest of your AppContent component
}

export default App;