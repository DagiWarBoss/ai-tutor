// frontend/src/Dashboard.jsx
import React, { useContext } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext'; // Import useAuth hook

const Dashboard = () => {
    const { currentUser } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        try {
            // If you have Firebase auth.signOut(), uncomment this:
            // await auth.signOut();
            localStorage.clear(); // Clear all local storage
            navigate('/login');
        } catch (error) {
            console.error("Failed to log out:", error);
        }
    };

    return (
        <div className="min-h-screen bg-gray-100 flex flex-col items-center py-10">
            <header className="w-full max-w-4xl bg-white shadow-md rounded-lg p-6 mb-8 flex justify-between items-center">
                <h1 className="text-4xl font-extrabold text-gray-800">AI Tutor Dashboard</h1>
                <nav>
                    <ul className="flex space-x-6">
                        <li>
                            <Link to="/upload-syllabus" className="text-blue-600 hover:text-blue-800 font-semibold text-lg transition duration-200">
                                Upload Syllabus
                            </Link>
                        </li>
                        <li>
                            <Link to="/generate-problem" className="text-green-600 hover:text-green-800 font-semibold text-lg transition duration-200">
                                Generate Problem
                            </Link>
                        </li>
                        <li>
                            <Link to="/quiz" className="text-purple-600 hover:text-purple-800 font-semibold text-lg transition duration-200">
                                Start Quiz
                            </Link>
                        </li>
                        <li>
                            <button
                                onClick={handleLogout}
                                className="text-red-600 hover:text-red-800 font-semibold text-lg transition duration-200 bg-transparent border-none cursor-pointer"
                            >
                                Logout
                            </button>
                        </li>
                    </ul>
                </nav>
            </header>

            <main className="w-full max-w-4xl bg-white shadow-md rounded-lg p-8">
                {currentUser && (
                    <h2 className="text-2xl font-bold text-gray-700 mb-6 text-center">
                        Welcome, {currentUser.email}!
                    </h2>
                )}

                <p className="text-gray-600 text-lg text-center mb-8">
                    Choose an option from the navigation above to get started.
                </p>

                {/* This version of Dashboard does NOT render dynamic subject lists */}
            </main>
        </div>
    );
};

export default Dashboard;