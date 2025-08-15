import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import ReactMarkdown from 'react-markdown';

// --- (Helper components like Spinner, MarkdownRenderer, QuizView remain the same) ---

// --- Main Component ---
export default function SyllabusExplorer() {
    // ... (Syllabus, loading, error, and selection states are the same)
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
    
    // --- ADD NEW STATE FOR CONTEXT SOURCE ---
    const [sourceName, setSourceName] = useState('');
    const [sourceLevel, setSourceLevel] = useState('');

    useEffect(() => {
        // ... (fetchSyllabus logic is the same)
    }, []);

    const resetContent = () => {
        setContent(null);
        setContentType(null);
        setError(null);
        // --- RESET SOURCE STATE ---
        setSourceName('');
        setSourceLevel('');
    };
    
    // ... (handleSubjectClick, handleChapterClick, handleTopicClick are the same)

    const fetchContent = async (topic, mode) => {
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

            // --- UPDATE STATE WITH SOURCE INFO ---
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

    // ... (Loading and error return statements remain the same)

    return (
        <div className="min-h-screen bg-gray-900 text-white p-4 sm:p-8 font-sans">
            {/* ... (Header is the same) ... */}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
                {/* ... (Left Side: 3-Pane Explorer is the same) ... */}

                {/* Right Side: Content Panel */}
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 h-[70vh] overflow-y-auto lg-col-span-1">
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

                            {/* --- ADD THE SOURCE DISPLAY ELEMENT --- */}
                            {sourceName && !isLoadingContent && (
                                <div className="text-xs text-gray-500 mb-4 p-2 bg-gray-900/50 rounded-md">
                                    <span className="font-bold">Source:</span> {sourceName} 
                                    <span className="italic"> ({sourceLevel} Context)</span>
                                </div>
                            )}

                            {content && (
                                <>
                                    {contentType === 'practice' 
                                        ? <QuizView quizData={content} onNext={() => fetchContent(selectedTopic, 'practice')} /> 
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
             {/* ... (Footer link is the same) ... */}
        </div>
    );
}