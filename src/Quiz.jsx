// src/Quiz.jsx
import React, { useEffect, useState } from "react";
import { useParams } from 'react-router-dom'; // <--- ADD THIS LINE

export default function Quiz() {
  const { subject } = useParams();
  const [questions, setQuestions] = useState([]);

  useEffect(() => {
    setQuestions(JSON.parse(localStorage.getItem(`${subject}-quiz`)));
  }, [subject]);

  return (
    <div style={{ color: '#000' }}> {/* Added inline style for visibility, remove if you have global CSS */}
      <h3>Quiz for {subject}</h3> {/* Added a heading for clarity */}
      {questions && questions.length > 0 ? ( // Check if questions exist before mapping
        questions.map((q, i) => (
          <div key={i} style={{ marginBottom: '15px', border: '1px solid #eee', padding: '10px', borderRadius: '5px' }}>
            <h4>{q.question}</h4>
            <div style={{ display: 'flex', gap: '10px' }}>
              {q.options.map((opt, j) => (
                <button key={j} onClick={() => alert(j === q.answer ? "Correct!" : "Wrong")}>
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))
      ) : (
        <p>No questions found for this subject. Try generating some!</p>
      )}
    </div>
  );
}