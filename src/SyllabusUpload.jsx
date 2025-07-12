// src/SyllabusUpload.jsx

import React, { useState } from 'react';
import axios from 'axios';

// Fix: Accept onUploadSuccess as a prop in the function signature
export default function SyllabusUpload({ onUploadSuccess }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadMessage, setUploadMessage] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [extractedSyllabusId, setExtractedSyllabusId] = useState(null); // To store the ID returned by backend

    const handleFileChange = (event) => {
        // Only allow PDF files
        if (event.target.files[0] && event.target.files[0].type === "application/pdf") {
            setSelectedFile(event.target.files[0]);
            setUploadMessage('');
        } else {
            setSelectedFile(null);
            setUploadMessage('Please select a PDF file.');
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) {
            setUploadMessage('Please select a file first.');
            return;
        }

        setIsUploading(true);
        setUploadMessage('Uploading and processing syllabus...');
        setExtractedSyllabusId(null);

        const formData = new FormData();
        formData.append('file', selectedFile); // 'file' must match the parameter name in your FastAPI endpoint (file: UploadFile = File(...))

        try {
            // Replace with your FastAPI backend URL.
            // If running locally, it's usually http://127.0.0.1:8000
            const response = await axios.post('http://127.0.0.1:8000/upload-syllabus/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            console.log('SyllabusUpload: Upload successful, response data:', response.data); // Added log
            const newSyllabusId = response.data.syllabus_id; // Get the ID from the response
            setUploadMessage(`✅ Success! Syllabus processed. ID: ${newSyllabusId}`);
            setExtractedSyllabusId(newSyllabusId); // Store the ID for local display
            setSelectedFile(null); // Clear selected file after successful upload

            // Fix: Call the onUploadSuccess prop to send the ID back to AppContent
            console.log('SyllabusUpload: Calling onUploadSuccess with ID:', newSyllabusId); // Added log
            if (onUploadSuccess) {
                onUploadSuccess(newSyllabusId);
            }

        } catch (error) {
            console.error('Error uploading syllabus:', error.response ? error.response.data : error.message);
            setUploadMessage(`❌ Upload failed: ${error.response ? error.response.data.detail || error.message : error.message}`);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div style={{ padding: '20px', maxWidth: '800px', margin: 'auto', color: '#fff' }}>
            <h2>Upload Syllabus</h2>
            <p>Upload your course syllabus here (PDF only). The AI will process it to generate personalized practice problems and quizzes.</p>

            <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                style={{ margin: '15px 0', display: 'block', color: '#fff' }}
            />

            {selectedFile && (
                <p>Selected file: {selectedFile.name}</p>
            )}

            <button
                onClick={handleUpload}
                disabled={!selectedFile || isUploading}
                style={{ padding: '10px 20px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
            >
                {isUploading ? 'Uploading...' : 'Upload Syllabus'}
            </button>

            {uploadMessage && <p style={{ marginTop: '15px', color: uploadMessage.startsWith('❌') ? 'red' : 'green' }}>{uploadMessage}</p>}

            {extractedSyllabusId && (
                <p style={{ marginTop: '10px', fontSize: '0.9em' }}>
                    You can use this Syllabus ID for problem generation: <strong>{extractedSyllabusId}</strong>
                </p>
            )}
        </div>
    );
}