// frontend/src/SyllabusUpload.jsx

import React, { useState, useContext } from 'react';
import axios from 'axios';
import { AuthContext } from './AuthContext';
import { AppContentContext } from './AppContentContext'; // NEW: Import AppContentContext
import '../index.css';

const SyllabusUpload = () => {
    const { currentUser } = useContext(AuthContext);
    const { setLastUploadedSyllabusId } = useContext(AppContentContext); // NEW: Get setter from context
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadMessage, setUploadMessage] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleFileChange = (event) => {
        setSelectedFile(event.target.files[0]);
        setUploadMessage('');
        setError('');
    };

    const handleUpload = async () => {
        if (!selectedFile) {
            setError('Please select a PDF file to upload.');
            return;
        }

        setLoading(true);
        setUploadMessage('');
        setError('');

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await axios.post(
                'http://127.0.0.1:8000/upload-syllabus/',
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                        // You might need an Authorization header here if your backend requires authentication
                        // 'Authorization': `Bearer ${currentUser?.token}`
                    },
                }
            );

            setUploadMessage(response.data.message + ` Syllabus ID: ${response.data.syllabus_id}`);
            setLastUploadedSyllabusId(response.data.syllabus_id); // NEW: Store ID in context
            setSelectedFile(null); // Clear the selected file input
        } catch (err) {
            console.error('Error uploading syllabus:', err);
            setError(err.response?.data?.detail || 'Failed to upload syllabus. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container mx-auto p-4 max-w-2xl bg-white rounded-lg shadow-md mt-10">
            <h1 className="text-3xl font-bold mb-6 text-gray-800 text-center">Syllabus Upload</h1>
            <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="syllabusFile">
                    Upload Syllabus (PDF only)
                </label>
                <input
                    id="syllabusFile"
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                />
            </div>
            <button
                onClick={handleUpload}
                className={`w-full py-2 px-4 rounded focus:outline-none focus:shadow-outline transition duration-200 
                    ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-500 hover:bg-green-700 text-white font-bold'}`}
                disabled={loading || !selectedFile}
            >
                {loading ? 'Uploading...' : 'Upload Syllabus'}
            </button>

            {uploadMessage && <p className="text-green-500 mt-4 text-center">{uploadMessage}</p>}
            {error && <p className="text-red-500 mt-4 text-center">{error}</p>}
        </div>
    );
};

export default SyllabusUpload;