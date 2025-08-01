// frontend/src/Dashboard.jsx
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

const Dashboard = () => {
    const { currentUser } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        try {
            // This is a placeholder for a real logout function
            localStorage.clear();
            navigate('/auth');
        } catch (error) {
            console.error("Failed to log out:", error);
        }
    };

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center p-4 font-sans">
            <div className="w-full max-w-5xl">
                <header className="bg-gray-800 shadow-md rounded-lg p-6 mb-8 flex justify-between items-center border border-gray-700">
                    <h1 className="text-3xl font-bold text-cyan-400">AI Tutor Dashboard</h1>
                    <nav>
                        <ul className="flex items-center space-x-6">
                            {/* NEW LINK to the Syllabus Explorer */}
                            <li>
                                <Link to="/syllabus" className="text-cyan-400 hover:text-cyan-300 font-semibold text-lg transition duration-200">
                                    Syllabus Explorer
                                </Link>
                            </li>
                            <li>
                                <Link to="/generate-problem" className="text-purple-400 hover:text-purple-300 font-semibold text-lg transition duration-200">
                                    Generate Problem
                                </Link>
                            </li>
                            <li>
                                <Link to="/quiz" className="text-green-400 hover:text-green-300 font-semibold text-lg transition duration-200">
                                    Start Quiz
                                </Link>
                            </li>
                            <li>
                                <button
                                    onClick={handleLogout}
                                    className="text-red-500 hover:text-red-400 font-semibold text-lg transition duration-200 bg-transparent border-none cursor-pointer"
                                >
                                    Logout
                                </button>
                            </li>
                        </ul>
                    </nav>
                </header>

                <main className="w-full bg-gray-800 shadow-md rounded-lg p-8 border border-gray-700">
                    {currentUser && (
                        <h2 className="text-2xl font-bold text-gray-300 mb-6 text-center">
                            Welcome, <span className="text-cyan-400">{currentUser.email}</span>!
                        </h2>
                    )}

                    <p className="text-gray-400 text-lg text-center mb-8">
                        This is your central hub for JEE preparation. Choose an option from the navigation above to get started.
                    </p>

                    <div className="text-center text-gray-500">
                        <p>[Future home of the 'Overall Progress Snapshot' and 'Today's Focus' panels]</p>
                    </div>
                </main>
            </div>
        </div>
    );
};

export default Dashboard;
