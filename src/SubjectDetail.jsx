import React from "react";
import { useParams, useNavigate } from "react-router-dom";

export default function SubjectDetail() {
  const { name } = useParams();
  const navigate = useNavigate();

  return (
    <div style={{ padding: "2rem" }}>
      <button onClick={() => navigate("/dashboard")} style={{ marginBottom: "1rem" }}>
        ⬅ Back to Dashboard
      </button>
      <h2>{name} Overview</h2>

      <div style={{ marginTop: "1rem" }}>
        <h3>🧠 Smart Suggestions (Coming Soon)</h3>
        <p>AI will analyze your syllabus and recommend topics, resources, and revision tasks.</p>
      </div>

      <div style={{ marginTop: "2rem" }}>
        <h3>📝 Notes</h3>
        <p>No notes yet. You’ll be able to add custom notes here.</p>
      </div>

      <div style={{ marginTop: "2rem" }}>
        <h3>✅ Tasks</h3>
        <p>No tasks yet. You’ll be able to track your progress here soon.</p>
      </div>

      <div style={{ marginTop: "2rem" }}>
        <h3>📈 Progress</h3>
        <p>Graphs and revision streaks will appear here in Beta phase.</p>
      </div>
    </div>
  );
}
