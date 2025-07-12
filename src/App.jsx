// src/App.jsx

// ... (existing imports and AppContent component) ...

function AppContent() {
    // ... (existing code) ...

    return (
        <div className="app-container">
            {/* Simple Navigation Bar */}
            <nav className="main-nav">
                <ul>
                    <li><Link to="/">Dashboard</Link></li>
                    {/* Modify this Link to pass the syllabus ID */}
                    <li>
                        <Link
                            to={{
                                pathname: "/generate-problem",
                                // state: { syllabusId: extractedSyllabusId } // Old way for react-router-dom v5
                                // For react-router-dom v6, use 'state' on the Link component
                                state: { syllabusId: "cb1095e5-f82c-4002-83d5-024acbb49f18" } // Replace with dynamic ID later
                            }}
                        >
                            Generate Problem
                        </Link>
                    </li>
                    <li><Link to="/quiz">Quiz</Link></li>
                    <li><Link to="/syllabus-upload">Syllabus Upload</Link></li>
                    {/* ... (rest of your nav) ... */}
                </ul>
            </nav>

            {/* ... (rest of AppContent return) ... */}
        </div>
    );
}

// ... (main App component) ...