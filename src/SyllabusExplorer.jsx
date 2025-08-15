import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import ReactMarkdown from 'react-markdown'; // Import the new library

// --- Helper Components ---
const Spinner = ({ text = "Loading..." }) => (
    <div className="flex flex-col justify-center items-center p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
        <p className="mt-4 text-gray-400">{text}</p>
    </div>
);

// New component to handle Markdown and LaTeX rendering together
const MarkdownRenderer = ({ markdown }) => {
    return (
        <ReactMarkdown
            className="prose prose-invert prose-p:text-gray-300 prose-headings:text-cyan-400"
            components={{
                // This custom component finds and renders LaTeX within the Markdown
                p: ({ node, ...props }) => {
                    const text = node.children[0].value;
                    const parts = text.split(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);
                    return (
                        <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                            {parts.map((part, index) => {
                                if (part.startsWith('$$') && part.endsWith('$$')) {
                                    return <BlockMath key={index} math={part.slice(2, -2)} />;
                                } else if (part.startsWith('$') && part.endsWith('$')) {
                                    return <InlineMath key={index} math={part.slice(1, -1)} />;
                                }
                                return <span key={index}>{part}</span>;
                            })}
                        </p>
                    );
                }
            }}
        >
            {markdown}
        </ReactMarkdown>
    );
};

const QuizView = ({ quizData, onNext }) => {
    // ... (QuizView component remains exactly the same as before)
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [isRevealed, setIsRevealed] = useState(false);

    const handleAnswerClick = (optionKey) => {
        if (!isRevealed) {
            setSelectedAnswer(optionKey);
        }
    };

    const getButtonClass = (optionKey) => {
        if (!isRevealed) {
            return selectedAnswer === optionKey ? 'bg-cyan-700' : 'bg-gray-700 hover:bg-cyan-800/50';
        }
        if (optionKey === quizData.correct_answer) {
            return 'bg-green-700'; // Correct answer
        }
        if (selectedAnswer === optionKey && optionKey !== quizData.correct_answer) {
            return 'bg-red-700'; // Incorrectly selected answer
        }
        return 'bg-gray-700'; // Other options
    };
    
    // Quick fix to re-render component when quizData changes
    useEffect(() => {
        setSelectedAnswer(null);
        setIsRevealed(false);
    }, [quizData]);


    return (
        <div className="space-y-4">
            <MarkdownRenderer markdown={quizData.question} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {Object.entries(quizData.options).map(([key, value]) => (
                    <button
                        key={key}
                        onClick={() => handleAnswerClick(key)}
                        className={`p-3 rounded-lg text-left transition-colors duration-200 ${getButtonClass(key)}`}
                    >
                       <span className="font-bold mr-2">{key}.</span> <MarkdownRenderer markdown={value} />
                    </button>
                ))}
            </div>
            <div className="pt-4 flex items-center space-x-4">
                 <button 
                    onClick={() => setIsRevealed(true)}
                    disabled={!selectedAnswer || isRevealed}
                    className="px-4 py-2 bg-purple-600 rounded-md disabled:bg-gray-600 disabled:cursor-not-allowed hover:bg-purple-700"
                >
                    Check Answer
                </button>
                 <button 
                    onClick={onNext}
                    className="px-4 py-2 bg-cyan-600 rounded-md hover:bg-cyan-700"
                >
                    Next Question
                </button>
            </div>
            {isRevealed && (
                <div className="mt-4 p-4 bg-gray-900 rounded-lg border border-gray-700">
                    <h3 className="font-bold text-lg text-cyan-400">Explanation</h3>
                    <MarkdownRenderer markdown={quizData.explanation} />
                </div>
            )}
        </div>
    );
};


// --- Main Component ---
export default function SyllabusExplorer() {
    // ... (State declarations remain the same as before)
    const [syllabus, setSyllabus] = useState([]);
    const [isLoadingSyllabus, setIsLoadingSyllabus] = useState(true);
    const [error, setError] = useState(null);
    const [selectedSubject, setSelectedSubject] = useState(null);
    const [selectedChapter, setSelectedChapter] = useState(null);
    const [selectedTopic, setSelectedTopic] = useState(null);
    const [content, setContent] = useState(null);
    const [contentType, setContentType] = useState(null);
    const [isLoadingContent, setIsLoadingContent] = useState(false);
    const [activeMode, setActiveMode] = useState(null);


    useEffect(() => {
        const fetchSyllabus = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/syllabus');
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                setSyllabus(data);
                if (data && data.length > 0) {
                    setSelectedSubject(data[0]);
                }
            } catch (e) {
                setError(e.message);
            } finally {
                setIsLoadingSyllabus(false);
            }
        };
        fetchSyllabus();
    }, []);

    const resetContent = () => {
        setContent(null);
        setContentType(null);
        setError(null);
    };
    
    const handleSubjectClick = (subject) => {
        setSelectedSubject(subject);
        setSelectedChapter(null);
        setSelectedTopic(null);
        resetContent();
        setActiveMode(null);
    };

    const handleChapterClick = (chapter) => {
        setSelectedChapter(chapter);
        setSelectedTopic(null);
        resetContent();
        setActiveMode(null);
    };
    
    // --- THIS IS THE UPDATED FUNCTION ---
    // It no longer fetches content automatically. It just selects the topic.
    const handleTopicClick = (topic) => {
        setSelectedTopic(topic);
        resetContent();
        setActiveMode(null); // Deselect any active mode button
    };

    const fetchContent = async (topic, mode) => {
        // ... (fetchContent function remains exactly the same as before)
        if (!topic) return;
        setIsLoadingContent(true);
        resetContent();
        setActiveMode(mode);
        try {
            const response = await fetch('http://localhost:8000/api/generate-content', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: topic.name, mode: mode }),
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (mode === 'practice') {
                setContent(data);
                setContentType('practice');
            } else {
                setContent(data.content);
                setContentType(mode);
            }
        } catch (e) {
            setError(e.message);
        } finally {
            setIsLoadingContent(false);
        }
    };

    // ... (Loading and error return statements remain the same)
    if (isLoadingSyllabus) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><Spinner text="Loading Syllabus..." /></div>;
    }

    if (error && !content) {
        return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><p className="text-red-500">Error: {error}</p></div>;
    }


    return (
        <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 font-sans">
            <header className="text-center mb-8">
                <h1 className="text-4xl font-bold text-cyan-400">PraxisAI</h1>
                <p className="text-gray-400 mt-2">Your AI-Powered JEE Study Partner. Select a topic to begin.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
                {/* Left Side: 3-Pane Explorer (No changes here) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:col-span-1">
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Subjects</h2>
                        <ul>{syllabus.map((subject) => (<li key={subject.id} onClick={() => handleSubjectClick(subject)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedSubject?.id === subject.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>{subject.name} (Class {subject.class_level})</li>))}</ul>
                    </div>
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Chapters</h2>
                        {selectedSubject ? (<ul>{selectedSubject.chapters.map((chapter) => (<li key={chapter.id} onClick={() => handleChapterClick(chapter)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedChapter?.id === chapter.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>Ch. {chapter.number}: {chapter.name}</li>))}</ul>) : <p className="text-gray-500 text-sm">Select a subject.</p>}
                    </div>
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Topics</h2>
                        {selectedChapter ? (<ul>{selectedChapter.topics.map((topic) => (<li key={topic.id} onClick={() => handleTopicClick(topic)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedTopic?.id === topic.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>{topic.number} {topic.name}</li>))}</ul>) : <p className="text-gray-500 text-sm">Select a chapter.</p>}
                    </div>
                </div>

                {/* Right Side: Content Panel */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 h-[70vh] overflow-y-auto lg:col-span-1">
                    {selectedTopic ? (
                        <>
                            <div className="border-b border-gray-700 pb-4 mb-4">
                                <h2 className="text-xl font-semibold text-cyan-300">{selectedTopic.name}</h2>
                                <div className="flex items-center space-x-2 mt-4">
                                    <button onClick={() => fetchContent(selectedTopic, 'explain')} className={`px-3 py-1 text-sm rounded-md ${activeMode === 'explain' ? 'bg-cyan-600' : 'bg-gray-700 hover:bg-gray-600'}`}>🧠 Learn</button>
                                    <button onClick={() => fetchContent(selectedTopic, 'revise')} className={`px-3 py-1 text-sm rounded-md ${activeMode === 'revise' ? 'bg-cyan-600' : 'bg-gray-700 hover:bg-gray-600'}`}>✨ Revise</button>
                                    <button onClick={() => fetchContent(selectedTopic, 'practice')} className={`px-3 py-1 text-sm rounded-md ${activeMode === 'practice' ? 'bg-cyan-600' : 'bg-gray-700 hover:bg-gray-600'}`}>📝 Practice</button>
                                </div>
                            </div>
                            {isLoadingContent && <Spinner />}
                            {error && <p className="text-red-500">Error: {error}</p>}
                            {content && (
                                <>
                                    {contentType === 'practice' 
                                        ? <QuizView quizData={content} onNext={() => fetchContent(selectedTopic, 'practice')} /> 
                                        // --- THIS IS THE UPDATED RENDERER ---
                                        : <MarkdownRenderer markdown={content} />
                                    }
                                </>
                            )}
                        </>
                    ) : (
                        <div className="flex justify-center items-center h-full">
                            <p className="text-gray-500">Select a topic to get started.</p>
                        </div>
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