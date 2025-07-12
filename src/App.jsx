// src/App.jsx

import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import ProtectedRoute from './ProtectedRoute.jsx';
import { auth } from './firebase';

import ProblemGenerator from "./ProblemGenerator.jsx";
import Dashboard from "./Dashboard.jsx";
import Quiz from "./Quiz.jsx";
import AuthPage from "./AuthPage.jsx";
import SyllabusUpload from "./SyllabusUpload.jsx";

function AppContent() {
    const navigate = useNavigate();
    const { currentUser, loading } = useAuth();
    const [lastUploadedSyllabusId, setLastUploadedSyllabusId] = useState(null);

    // *** ADD THIS WRAPPER FUNCTION ***
    const handleSetLastUploadedSyllabusId = (id) => {
        console.log("AppContent: Attempting to set lastUploadedSyllabusId to:", id);
        setLastUploadedSyllabusId(id);
        // This log will show the *new* state after the setter has potentially run
        // Due to React's async nature, it might not immediately reflect,
        // but the main AppContent log will later confirm.
    };

    console.log("AppContent - currentUser:", currentUser);
    console.log("AppContent - loading:", loading);
    console.log("AppContent - lastUploadedSyllabusId (during render):", lastUploadedSyllabusId); // Keep this log
    console.log("AppContent: setLastUploadedSyllabusId function:", setLastUploadedSyllabusId); // Keep this log

    const handleLogout = async () => {
        try {
            await auth.signOut();
            console.log("User logged out via Firebase!");
            navigate('/auth');
        } catch (error) {
            console.error("Error logging out:", error);
        }
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'white' }}>
                Loading application...
            </div>
        );
    }

    return (
        <div className="app-container">
            <nav className="main-nav">
                <ul>
                    <li><Link to="/">Dashboard</Link></li>
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

            <Routes>
                <Route path="/auth" element={<AuthPage />} />
                <Route path="/" element={<ProtectedRoute><Dashboard handleLogout={handleLogout} /></ProtectedRoute>} />
                <Route path="/generate-problem" element={<ProtectedRoute><ProblemGenerator /></ProtectedRoute>} />
                <Route path="/quiz" element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
                <Route
                    path="/syllabus-upload"
                    element={
                        <ProtectedRoute>
                            {/* *** USE THE WRAPPER FUNCTION HERE *** */}
                            <SyllabusUpload onUploadSuccess={handleSetLastUploadedSyllabusId} />
                        </ProtectedRoute>
                    }
                />
            </Routes>
        </div>
    );
}

function App() {
    return (
        <Router>
            <AuthProvider>
                <AppContent />
            </AuthProvider>
        </Router>
    );
}

export default App;