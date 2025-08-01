import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

// Simple loading spinner component
const Spinner = () => (
    <div className="flex justify-center items-center p-8">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-cyan-400"></div>
    </div>
);

export default function SyllabusExplorer() {
    const [syllabus, setSyllabus] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const [selectedSubject, setSelectedSubject] = useState(null);
    const [selectedChapter, setSelectedChapter] = useState(null);

    useEffect(() => {
        const fetchSyllabus = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/syllabus');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setSyllabus(data);
            } catch (e) {
                setError(e.message);
                console.error("Failed to fetch syllabus:", e);
            } finally {
                setIsLoading(false);
            }
        };

        fetchSyllabus();
    }, []); // Empty dependency array means this runs once on mount

    const handleSubjectClick = (subject) => {
        setSelectedSubject(subject);
        setSelectedChapter(null); // Reset chapter selection when a new subject is chosen
    };
    
    const handleChapterClick = (chapter) => {
        setSelectedChapter(chapter);
    };

    if (isLoading) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><Spinner /></div>;
    }

    if (error) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><p className="text-red-500">Error loading syllabus: {error}</p></div>;
    }

    return (
        <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 font-sans">
            <header className="text-center mb-8">
                <h1 className="text-4xl font-bold text-cyan-400">Syllabus Explorer</h1>
                <p className="text-gray-400 mt-2">Browse the complete NCERT syllabus for your JEE preparation.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-7xl mx-auto">
                {/* Pane 1: Subjects */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                    <h2 className="text-xl font-semibold mb-4 text-cyan-300 border-b border-gray-700 pb-2">Subjects</h2>
                    <ul>
                        {syllabus.map((subject) => (
                            <li key={subject.id} 
                                onClick={() => handleSubjectClick(subject)}
                                className={`p-3 rounded-md cursor-pointer transition-colors duration-200 ${selectedSubject?.id === subject.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}
                            >
                                {subject.name} (Class {subject.class_level})
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Pane 2: Chapters */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                    <h2 className="text-xl font-semibold mb-4 text-cyan-300 border-b border-gray-700 pb-2">Chapters</h2>
                    {selectedSubject ? (
                        <ul>
                            {selectedSubject.chapters.map((chapter) => (
                                <li key={chapter.id}
                                    onClick={() => handleChapterClick(chapter)}
                                    className={`p-3 rounded-md cursor-pointer transition-colors duration-200 ${selectedChapter?.id === chapter.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}
                                >
                                    {chapter.number}. {chapter.name}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-gray-500 mt-4">Select a subject to see its chapters.</p>
                    )}
                </div>

                {/* Pane 3: Topics */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                    <h2 className="text-xl font-semibold mb-4 text-cyan-300 border-b border-gray-700 pb-2">Topics</h2>
                    {selectedChapter ? (
                         <ul>
                            {selectedChapter.topics.map((topic) => (
                                <li key={topic.id} className="p-3 text-gray-400">
                                    {topic.number} {topic.name}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-gray-500 mt-4">Select a chapter to see its topics.</p>
                    )}
                </div>
            </div>
             <div className="text-center mt-8">
                <Link to="/dashboard" className="text-purple-400 hover:text-purple-300 font-semibold transition-colors duration-200">
                    &larr; Back to Dashboard
                </Link>
            </div>
        </div>
    );
}
