import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import ReactMarkdown from 'react-markdown';

// --- Here are the complete, unabridged helper components ---
const Spinner = ({ text = "Loading..." }) => (
    <div className="flex flex-col justify-center items-center p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
        <p className="mt-4 text-gray-400">{text}</p>
    </div>
);

const MarkdownRenderer = ({ markdown }) => {
    return (
        <div className="prose prose-invert max-w-none prose-p:text-gray-300 prose-headings:text-cyan-400 prose-strong:text-white prose-ul:list-disc prose-li:text-gray-300">
            <ReactMarkdown
                components={{
                    p: ({ node, ...props }) => {
                        if (node.children[0]?.type === 'text') {
                            const text = node.children[0].value;
                            const parts = text.split(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);
                            return (
                                <p className="leading-relaxed my-2">
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
                        return <p {...props} className="leading-relaxed my-2" />;
                    }
                }}
            >
                {markdown}
            </ReactMarkdown>
        </div>
    );
};

const QuizView = ({ quizData, onNext }) => {
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [isRevealed, setIsRevealed] = useState(false);

    useEffect(() => {
        setSelectedAnswer(null);
        setIsRevealed(false);
    }, [quizData]);

    const handleAnswerClick = (optionKey) => {
        if (!isRevealed) {
            setSelectedAnswer(optionKey);
        }
    };
    
    const getButtonClass = (optionKey) => {
        if (!isRevealed) {
            return selectedAnswer === optionKey ? 'bg-cyan-700' : 'bg-gray-700 hover:bg-cyan-800/50';
        }
        const correctAnswerKey = quizData.correct_answer?.trim().toUpperCase().replace(/[^A-D]/g, '') || '';
        if (optionKey === correctAnswerKey) {
            return 'bg-green-700';
        }
        if (optionKey === selectedAnswer && optionKey !== correctAnswerKey) {
            return 'bg-red-700';
        }
        return 'bg-gray-700';
    };

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
                 <button onClick={() => setIsRevealed(true)} disabled={!selectedAnswer || isRevealed} className="px-4 py-2 bg-purple-600 rounded-md disabled:bg-gray-600 disabled:cursor-not-allowed hover:bg-purple-700">Check Answer</button>
                 <button onClick={onNext} className="px-4 py-2 bg-cyan-600 rounded-md hover:bg-cyan-700">Next Question</button>
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
    const [sourceName, setSourceName] = useState('');
    const [sourceLevel, setSourceLevel] = useState('');
    const chaptersRef = useRef(null);
    const topicsRef = useRef(null);

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

    useEffect(() => {
        if (selectedSubject && chaptersRef.current) {
            chaptersRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [selectedSubject]);

    useEffect(() => {
        if (selectedChapter && topicsRef.current) {
            topicsRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [selectedChapter]);

    const groupedChapters = useMemo(() => {
        if (!selectedSubject) return {};
        return selectedSubject.chapters.reduce((acc, chapter) => {
            const level = chapter.class_level;
            if (!acc[level]) acc[level] = [];
            acc[level].push(chapter);
            return acc;
        }, {});
    }, [selectedSubject]);

    const resetContent = () => {
        setContent(null); setContentType(null); setError(null);
        setSourceName(''); setSourceLevel('');
    };
    
    const handleSubjectClick = (subject) => {
        setSelectedSubject(subject); setSelectedChapter(null); setSelectedTopic(null);
        resetContent(); setActiveMode(null);
    };

    const handleChapterClick = (chapter) => {
        setSelectedChapter(chapter); setSelectedTopic(null);
        resetContent(); setActiveMode(null);
    };
    
    const handleTopicClick = (topic) => {
        setSelectedTopic(topic); resetContent(); setActiveMode(null);
    };

    const fetchContent = async (topic, mode) => {
        if (!topic) return;
        setIsLoadingContent(true); resetContent(); setActiveMode(mode);
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
            setSourceName(data.source_name || '');
            setSourceLevel(data.source_level || '');
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

    if (isLoadingSyllabus) return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><Spinner text="Loading Syllabus..." /></div>;
    if (error && !content) return <div className="min-h-screen bg-gray-900 text-white flex justify-center items-center"><p className="text-red-500">Error: {error}</p></div>;

    return (
        <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 font-sans">
            <header className="text-center mb-8">
                <h1 className="text-4xl font-bold text-cyan-400">PraxisAI</h1>
                <p className="text-gray-400 mt-2">Your Personal AI Tutor for JEE Prep</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:col-span-1">
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Subjects</h2>
                        <ul>
                            {syllabus.map((subject) => (
                                <li key={subject.id} onClick={() => handleSubjectClick(subject)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedSubject?.id === subject.id ? 'bg-cyan-600 font-bold' : 'hover:bg-gray-700'}`}>
                                    {subject.name}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div ref={chaptersRef} className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Chapters</h2>
                        {selectedSubject ? (
                            Object.keys(groupedChapters).sort().map(level => (
                                <div key={level}>
                                    <h3 className="text-md font-bold text-gray-400 mt-4 mb-2 sticky top-0 bg-gray-800 py-1">Class {level}</h3>
                                    <ul>
                                        {groupedChapters[level].map((chapter) => (
                                            <li key={chapter.id} onClick={() => handleChapterClick(chapter)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedChapter?.id === chapter.id ? 'bg-cyan-600 font-bold' : 'hover:bg-gray-700'}`}>
                                                Ch. {chapter.number}: {chapter.name}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))
                        ) : ( <p className="text-gray-500 text-sm">Select a subject.</p> )}
                    </div>
                    <div ref={topicsRef} className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Topics</h2>
                        {selectedChapter ? (<ul>{selectedChapter.topics.map((topic) => (<li key={topic.id} onClick={() => handleTopicClick(topic)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedTopic?.id === topic.id ? 'bg-cyan-600 font-bold' : 'hover:bg-gray-700'}`}>{topic.number} {topic.name}</li>))}</ul>) : <p className="text-gray-500 text-sm">Select a chapter.</p>}
                    </div>
                </div>
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
                            {sourceName && !isLoadingContent && ( <div className="text-xs text-gray-500 mb-4 p-2 bg-gray-900/50 rounded-md"><span className="font-bold">Source:</span> {sourceName} <span className="italic"> ({sourceLevel} Context)</span></div>)}
                            {content && (
                                <>
                                    {contentType === 'practice' 
                                        ? <QuizView quizData={content} onNext={() => fetchContent(selectedTopic, 'practice')} /> 
                                        : <MarkdownRenderer markdown={content} />
                                    }
                                </>
                            )}
                        </>
                    ) : ( <div className="flex justify-center items-center h-full"><p className="text-gray-500">Select a topic to get started.</p></div> )}
                </div>
            </div>
            <div className="text-center mt-8"><Link to="/dashboard" className="text-purple-400 hover:text-purple-300 font-semibold transition-colors duration-200">&larr; Back to Dashboard</Link></div>
        </div>
    );
}