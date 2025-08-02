import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

// --- Helper Components ---
const Spinner = ({ text = "Loading..." }) => (
    <div className="flex flex-col justify-center items-center p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
        <p className="mt-4 text-gray-400">{text}</p>
    </div>
);

const MathText = ({ text }) => {
    if (!text) return null;
    const parts = text.split(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);
    return (
        <div className="text-gray-300 whitespace-pre-wrap leading-relaxed">
            {parts.map((part, index) => {
                if (part.startsWith('$$') && part.endsWith('$$')) {
                    return <BlockMath key={index} math={part.slice(2, -2)} />;
                } else if (part.startsWith('$') && part.endsWith('$')) {
                    return <InlineMath key={index} math={part.slice(1, -1)} />;
                }
                return <span key={index}>{part}</span>;
            })}
        </div>
    );
};

// --- Main Component ---
export default function SyllabusExplorer() {
    const [syllabus, setSyllabus] = useState([]);
    const [isLoadingSyllabus, setIsLoadingSyllabus] = useState(true);
    const [error, setError] = useState(null);

    const [selectedSubject, setSelectedSubject] = useState(null);
    const [selectedChapter, setSelectedChapter] = useState(null);
    const [selectedTopic, setSelectedTopic] = useState(null);
    
    const [explanation, setExplanation] = useState('');
    const [isLoadingExplanation, setIsLoadingExplanation] = useState(false);
    const [sourceChapter, setSourceChapter] = useState('');

    // Effect to fetch the entire syllabus once on mount
    useEffect(() => {
        const fetchSyllabus = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/syllabus');
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                setSyllabus(data);
            } catch (e) {
                setError(e.message);
            } finally {
                setIsLoadingSyllabus(false);
            }
        };
        fetchSyllabus();
    }, []); // Empty array ensures this runs only once

    const handleTopicClick = async (topic) => {
        setSelectedTopic(topic);
        setIsLoadingExplanation(true);
        setExplanation('');
        setError(null);

        try {
            const response = await fetch('http://localhost:8000/ask-question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: `Explain the topic: ${topic.name} from the chapter on ${selectedChapter.name}` }),
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setExplanation(data.answer);
            setSourceChapter(data.source_chapter);
        } catch (e) {
            setError(e.message);
        } finally {
            setIsLoadingExplanation(false);
        }
    };

    if (isLoadingSyllabus) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><Spinner text="Loading Syllabus..." /></div>;
    }

    if (error && !explanation) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><p className="text-red-500">Error: {error}</p></div>;
    }

    return (
        <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 font-sans">
            <header className="text-center mb-8">
                <h1 className="text-4xl font-bold text-cyan-400">Interactive Syllabus</h1>
                <p className="text-gray-400 mt-2">Browse the syllabus and click on a topic to get an instant, grounded explanation.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
                {/* Left Side: 3-Pane Explorer */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:col-span-1">
                    {/* Pane 1: Subjects */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Subjects</h2>
                        <ul>
                            {syllabus.map((subject) => (
                                <li key={subject.id} onClick={() => { setSelectedSubject(subject); setSelectedChapter(null); setSelectedTopic(null); }}
                                    className={`p-2 rounded-md cursor-pointer text-sm ${selectedSubject?.id === subject.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>
                                    {subject.name} (Class {subject.class_level})
                                </li>
                            ))}
                        </ul>
                    </div>
                    {/* Pane 2: Chapters */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Chapters</h2>
                        {selectedSubject ? (
                            <ul>
                                {selectedSubject.chapters.map((chapter) => (
                                    <li key={chapter.id} onClick={() => { setSelectedChapter(chapter); setSelectedTopic(null); }}
                                        className={`p-2 rounded-md cursor-pointer text-sm ${selectedChapter?.id === chapter.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>
                                        Ch. {chapter.number}: {chapter.name}
                                    </li>
                                ))}
                            </ul>
                        ) : <p className="text-gray-500 text-sm">Select a subject.</p>}
                    </div>
                    {/* Pane 3: Topics */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Topics</h2>
                        {selectedChapter ? (
                            <ul>
                                {selectedChapter.topics.map((topic) => (
                                    <li key={topic.id} onClick={() => handleTopicClick(topic)}
                                        className={`p-2 rounded-md cursor-pointer text-sm ${selectedTopic?.id === topic.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>
                                        {topic.number} {topic.name}
                                    </li>
                                ))}
                            </ul>
                        ) : <p className="text-gray-500 text-sm">Select a chapter.</p>}
                    </div>
                </div>

                {/* Right Side: Explanation Panel */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 h-[70vh] overflow-y-auto lg:col-span-1">
                    <h2 className="text-xl font-semibold mb-4 text-cyan-300 border-b border-gray-700 pb-2">Explanation</h2>
                    {isLoadingExplanation && <Spinner text="Generating Explanation..." />}
                    {error && <p className="text-red-500">Error: {error}</p>}
                    {explanation ? (
                        <div>
                            <p className="text-sm text-gray-500 mb-4">
                                <span className="font-bold">Source Chapter:</span> {sourceChapter}
                            </p>
                            <MathText text={explanation} />
                        </div>
                    ) : (
                        !isLoadingExplanation && <p className="text-gray-500">Select a topic to see an explanation here.</p>
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
