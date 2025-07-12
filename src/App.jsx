// frontend/src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AuthPage from './AuthPage';
import Dashboard from './Dashboard';
import ProblemGenerator from './ProblemGenerator';
import SyllabusUpload from './SyllabusUpload';
import Quiz from './Quiz';
import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from './AuthContext'; // Assuming AuthProvider is also exported from AuthContext
import { AppContentProvider } from './AppContentContext'; // NEW: Import AppContentProvider
import './App.css';
import './index.css';

function App() {
  return (
    <Router>
      <AuthProvider> {/* AuthProvider wraps the entire application */}
        <AppContentProvider> {/* NEW: AppContentProvider wraps content needing syllabus ID */}
          <Routes>
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route 
              path="/dashboard" 
              element={<ProtectedRoute><Dashboard /></ProtectedRoute>} 
            />
            <Route 
              path="/generate-problem" 
              element={<ProtectedRoute><ProblemGenerator /></ProtectedRoute>} 
            />
            <Route 
              path="/syllabus-upload" 
              element={<ProtectedRoute><SyllabusUpload /></ProtectedRoute>} 
            />
            <Route 
              path="/quiz" 
              element={<ProtectedRoute><Quiz /></ProtectedRoute>} 
            />
            {/* Add other routes as needed */}
          </Routes>
        </AppContentProvider> {/* NEW: Close AppContentProvider */}
      </AuthProvider>
    </Router>
  );
}

export default App;