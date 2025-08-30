import React, { useState } from 'react';

const ImageSolver = () => {
  const [selectedImage, setSelectedImage] = useState(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

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
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedImage) {
      setError('Please select an image.');
      return;
    }
    
    if (!question.trim()) {
      setError('Please enter a question about the image.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setAnswer('');

    try {
      // Create FormData for multipart upload
      const formData = new FormData();
      formData.append('image', selectedImage);
      formData.append('question', question);

      const response = await fetch('http://localhost:8000/image-solve', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnswer(data.answer);
      
      // Clear the form
      setSelectedImage(null);
      setImagePreview(null);
      setQuestion('');
      
    } catch (err) {
      console.error("Failed to solve image problem:", err);
      setError(`Failed to solve image problem. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBase64Submit = async (e) => {
    e.preventDefault();
    
    if (!selectedImage) {
      setError('Please select an image.');
      return;
    }
    
    if (!question.trim()) {
      setError('Please enter a question about the image.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setAnswer('');

    try {
      // Convert image to base64
      const reader = new FileReader();
      reader.onload = async (e) => {
        const base64Data = e.target.result.split(',')[1]; // Remove data:image/...;base64, prefix
        
        const response = await fetch('http://localhost:8000/image-solve-base64', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question: question,
            image_data: base64Data
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setAnswer(data.answer);
        
        // Clear the form
        setSelectedImage(null);
        setImagePreview(null);
        setQuestion('');
      };
      
      reader.readAsDataURL(selectedImage);
      
    } catch (err) {
      console.error("Failed to solve image problem:", err);
      setError(`Failed to solve image problem. Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-4 font-sans">
      <div className="w-full max-w-4xl">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-cyan-400">AI Image Problem Solver</h1>
          <p className="text-gray-400 mt-2">
            Upload an image of a math problem, physics diagram, or chemistry equation and ask the AI to solve it!
          </p>
        </header>

        <form onSubmit={handleSubmit} className="w-full mb-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Image Upload Section */}
            <div className="space-y-4">
              <label className="block text-gray-300 text-sm font-bold mb-2">
                Upload Image
              </label>
              <div className="border-2 border-dashed border-gray-600 rounded-lg p-6 text-center hover:border-cyan-500 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  className="hidden"
                  id="imageInput"
                />
                <label htmlFor="imageInput" className="cursor-pointer">
                  {imagePreview ? (
                    <div className="space-y-2">
                      <img 
                        src={imagePreview} 
                        alt="Preview" 
                        className="max-w-full h-48 object-contain mx-auto rounded"
                      />
                      <p className="text-sm text-gray-400">Click to change image</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="text-4xl text-gray-400">📷</div>
                      <p className="text-gray-300">Click to upload image</p>
                      <p className="text-sm text-gray-500">Supports JPG, PNG, GIF</p>
                    </div>
                  )}
                </label>
              </div>
            </div>

            {/* Question Input Section */}
            <div className="space-y-4">
              <label className="block text-gray-300 text-sm font-bold mb-2">
                Your Question
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g., Solve this math problem, Explain this physics diagram, What's the chemical equation here?"
                className="w-full h-32 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition duration-200 resize-none"
              />
              
              <div className="flex space-x-3">
                <button
                  type="submit"
                  disabled={isLoading || !selectedImage || !question.trim()}
                  className="flex-1 bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-900 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg transition duration-200 shadow-lg shadow-cyan-600/20"
                >
                  {isLoading ? 'Solving...' : 'Solve with Multipart'}
                </button>
                
                <button
                  type="button"
                  onClick={handleBase64Submit}
                  disabled={isLoading || !selectedImage || !question.trim()}
                  className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-900 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg transition duration-200 shadow-lg shadow-purple-600/20"
                >
                  {isLoading ? 'Solving...' : 'Solve with Base64'}
                </button>
              </div>
            </div>
          </div>
        </form>

        {/* Answer Display */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 min-h-[200px]">
          {isLoading && (
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
              <p className="mt-4 text-gray-400">Analyzing image and generating solution...</p>
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
              <h3 className="text-xl font-bold text-cyan-400 mb-4">AI Solution:</h3>
              <div className="prose prose-invert max-w-none">
                <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">{answer}</p>
              </div>
            </div>
          )}

          {!isLoading && !error && !answer && (
            <div className="text-center text-gray-500">
              <p>Upload an image and ask a question to get started!</p>
            </div>
          )}
        </div>

        <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>AI Image Solver - Powered by JEE PCM Knowledge Base</p>
        </footer>
      </div>
    </div>
  );
};

export default ImageSolver;
