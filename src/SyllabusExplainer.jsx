import React, { useState } from 'react';

// A simple book icon for the button
const BookOpenIcon = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 3 0 0 1 3-3h7z"></path>
  </svg>
);

// Camera icon for image upload
const CameraIcon = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
);

export default function SyllabusExplainer() {
  // We'll now use a natural language question for the input
  const [question, setQuestion] = useState('why does a ball fall down?');
  const [answer, setAnswer] = useState('');
  const [sourceChapter, setSourceChapter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Image upload state
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [useImage, setUseImage] = useState(false);

  const handleImageChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedImage(file);
      setError(null);
      
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
      setUseImage(true);
    }
  };

  const removeImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    setUseImage(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question) {
      setError('Please enter a question.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setAnswer('');
    setSourceChapter('');

    try {
      let response;
      
      if (useImage && selectedImage) {
        // Use image-solve endpoint with multipart form data
        const formData = new FormData();
        formData.append('image', selectedImage);
        formData.append('question', question);

        response = await fetch('http://localhost:8000/image-solve', {
          method: 'POST',
          body: formData,
        });
      } else {
        // Use regular ask-question endpoint
        response = await fetch('http://localhost:8000/ask-question', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ question: question }),
        });
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnswer(data.answer);
      setSourceChapter(data.source_chapter || 'AI Analysis');

    } catch (err) {
      console.error("Failed to get answer:", err);
      setError(`Failed to get answer from the AI Tutor. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-4 font-sans">
      <div className="w-full max-w-4xl">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-cyan-400">AI Syllabus Explainer (Smart Test)</h1>
          <p className="text-gray-400 mt-2">Ask any question, and the AI will find the relevant chapter to answer it.</p>
        </header>

        <form onSubmit={handleSubmit} className="w-full mb-8">
          <div className="space-y-6">
            {/* Question Input */}
            <div>
              <label className="block text-gray-300 text-sm font-bold mb-2">
                Your Question
              </label>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g., why is the sky blue? or explain newton's laws"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition duration-200"
              />
            </div>

            {/* Image Upload Section */}
            <div>
              <label className="block text-gray-300 text-sm font-bold mb-2">
                Optional: Upload an Image
              </label>
              <div className="border-2 border-dashed border-gray-600 rounded-lg p-6 text-center hover:border-cyan-500 transition-colors">
                {!imagePreview ? (
                  <>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageChange}
                      className="hidden"
                      id="imageInput"
                    />
                    <label htmlFor="imageInput" className="cursor-pointer">
                      <div className="space-y-2">
                        <CameraIcon className="w-12 h-12 mx-auto text-gray-400" />
                        <p className="text-gray-300">Click to upload an image</p>
                        <p className="text-sm text-gray-500">Supports JPG, PNG, GIF</p>
                      </div>
                    </label>
                  </>
                ) : (
                  <div className="space-y-4">
                    <img 
                      src={imagePreview} 
                      alt="Preview" 
                      className="max-w-full h-48 object-contain mx-auto rounded"
                    />
                    <div className="flex space-x-3 justify-center">
                      <button
                        type="button"
                        onClick={removeImage}
                        className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition duration-200"
                      >
                        Remove Image
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Submit Button */}
            <div className="flex justify-center">
              <button
                type="submit"
                disabled={isLoading || !question.trim()}
                className="flex items-center justify-center bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-900 disabled:cursor-not-allowed text-white font-bold py-3 px-8 rounded-lg transition duration-200 shadow-lg shadow-cyan-600/20"
              >
                {useImage ? <CameraIcon className="w-5 h-5 mr-2" /> : <BookOpenIcon className="w-5 h-5 mr-2" />}
                {isLoading ? 'Thinking...' : useImage ? 'Ask About Image' : 'Ask Question'}
              </button>
            </div>
          </div>
        </form>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 min-h-[300px] flex items-center justify-center">
          {isLoading && (
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
              <p className="mt-4 text-gray-400">
                {useImage ? 'Analyzing image and searching knowledge base...' : 'Searching knowledge base and generating answer...'}
              </p>
            </div>
          )}

          {error && (
            <div className="text-red-400 bg-red-900/20 border border-red-700 rounded-lg p-4">
              <h3 className="font-bold mb-2">An Error Occurred</h3>
              <p>{error}</p>
            </div>
          )}

          {answer && (
            <div className="text-left w-full">
              {sourceChapter && (
                <p className="text-sm text-gray-500 mb-4 border-b border-gray-700 pb-2">
                  <span className="font-bold">Source Chapter:</span> {sourceChapter}
                </p>
              )}
              <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">{answer}</p>
            </div>
          )}

          {!isLoading && !error && !answer && (
            <p className="text-gray-500">The AI-generated answer will appear here.</p>
          )}
        </div>
         <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>AI Tutor Alpha v0.4 - Semantic Search RAG Pipeline with Image Support</p>
        </footer>
      </div>
    </div>
  );
}
