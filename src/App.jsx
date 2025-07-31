// frontend/src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AuthPage from './AuthPage';
import Dashboard from './Dashboard';
import ProblemGenerator from './ProblemGenerator';
import SyllabusUpload from './SyllabusUpload';
import Quiz from './Quiz';
import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from './AuthContext';
import { AppContentProvider } from './AppContentContext';
import SyllabusExplainer from './SyllabusExplainer'; // <-- 1. IMPORT THE NEW COMPONENT
import './App.css';
import './index.css';

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContentProvider>
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
            {/* 2. ADD THE NEW ROUTE FOR THE SMART TEST */}
            <Route 
              path="/smart-test" 
              element={<ProtectedRoute><SyllabusExplainer /></ProtectedRoute>} 
            />
          </Routes>
        </AppContentProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
