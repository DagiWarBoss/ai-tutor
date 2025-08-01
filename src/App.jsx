// frontend/src/App.jsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AuthPage from './AuthPage';
import Dashboard from './Dashboard';
import ProblemGenerator from './ProblemGenerator';
import Quiz from './Quiz';
import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from './AuthContext';
import { AppContentProvider } from './AppContentContext';
import SyllabusExplainer from './SyllabusExplainer'; // Make sure this is imported
import SyllabusExplorer from './SyllabusExplorer';   // Make sure this is imported too

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContentProvider>
          <Routes>
            {/* ... other routes ... */}
            <Route 
              path="/quiz" 
              element={<ProtectedRoute><Quiz /></ProtectedRoute>} 
            />
            
            {/* This is the route that was missing or incorrect */}
            <Route 
              path="/explain-syllabus" 
              element={<ProtectedRoute><SyllabusExplainer /></ProtectedRoute>} 
            />

            {/* This is the route for the 3-pane explorer */}
            <Route 
              path="/syllabus" 
              element={<ProtectedRoute><SyllabusExplorer /></ProtectedRoute>} 
            />
          </Routes>
        </AppContentProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;