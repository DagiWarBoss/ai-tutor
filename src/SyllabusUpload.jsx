import React, { useState } from "react";

export default function SyllabusUpload() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setStatus("");
  };

  const handleUpload = () => {
    if (!file) {
      setStatus("❌ No file selected.");
      return;
    }

    // Placeholder logic
    const allowedTypes = ["application/pdf", "text/plain"];
    if (!allowedTypes.includes(file.type)) {
      setStatus("❌ Please upload a PDF or TXT file.");
      return;
    }

    setStatus("✅ Syllabus uploaded (mocked).");
  };

  return (
    <div className="p-4 border rounded-xl shadow bg-white">
      <h3 className="text-lg font-bold mb-2">Upload Your Syllabus</h3>
      <input type="file" onChange={handleFileChange} className="mb-2" />
      <button
        onClick={handleUpload}
        className="bg-blue-600 text-white px-4 py-1 rounded hover:bg-blue-700"
      >
        Upload
      </button>
      {status && <p className="mt-2 text-sm">{status}</p>}
    </div>
  );
}
