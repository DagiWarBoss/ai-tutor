import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import ReactMarkdown from 'react-markdown';

// --- (Helper components: Spinner, MarkdownRenderer, QuizView remain the same) ---

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

    // NEW LOGIC: Group chapters of the selected subject by their class level
    const groupedChapters = useMemo(() => {
        if (!selectedSubject) return {};
        return selectedSubject.chapters.reduce((acc, chapter) => {
            const level = chapter.class_level;
            if (!acc[level]) {
                acc[level] = [];
            }
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
                    {/* SUBJECTS PANE: Simplified to a single list */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Subjects</h2>
                        <ul>
                            {syllabus.map((subject) => (
                                <li key={subject.id} onClick={() => handleSubjectClick(subject)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedSubject?.id === subject.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>
                                    {subject.name}
                                </li>
                            ))}
                        </ul>
                    </div>
                    {/* CHAPTERS PANE: Now grouped by class level */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Chapters</h2>
                        {selectedSubject ? (
                            Object.keys(groupedChapters).sort().map(level => (
                                <div key={level}>
                                    <h3 className="text-md font-bold text-gray-400 mt-4 mb-2 sticky top-0 bg-gray-800 py-1">Class {level}</h3>
                                    <ul>
                                        {groupedChapters[level].map((chapter) => (
                                            <li key={chapter.id} onClick={() => handleChapterClick(chapter)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedChapter?.id === chapter.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>
                                                Ch. {chapter.number}: {chapter.name}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))
                        ) : (
                            <p className="text-gray-500 text-sm">Select a subject.</p>
                        )}
                    </div>
                    {/* TOPICS PANE: No changes needed */}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 h-[70vh] overflow-y-auto">
                        <h2 className="text-lg font-semibold mb-4 text-cyan-300">Topics</h2>
                        {selectedChapter ? (<ul>{selectedChapter.topics.map((topic) => (<li key={topic.id} onClick={() => handleTopicClick(topic)} className={`p-2 rounded-md cursor-pointer text-sm ${selectedTopic?.id === topic.id ? 'bg-cyan-800/50' : 'hover:bg-gray-700'}`}>{topic.number} {topic.name}</li>))}</ul>) : <p className="text-gray-500 text-sm">Select a chapter.</p>}
                    </div>
                </div>

                {/* --- (Right Side Content Panel remains the same) --- */}
            </div>
            {/* --- (Footer link remains the same) --- */}
        </div>
    );
}