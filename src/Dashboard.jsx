import React, { useEffect, useState } from "react";

// Accept handleLogout as a prop
export default function Dashboard({ handleLogout }) {
  const userEmail = localStorage.getItem("user");
  const storageKey = `subjects_${userEmail}`;

  const [subjects, setSubjects] = useState(() => {
    const saved = localStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : [];
  });

  const [practiceSubjectIndex, setPracticeSubjectIndex] = useState(null);

  // Update localStorage on change
  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(subjects));
  }, [subjects, storageKey]);

  const handleUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const lines = event.target.result
        .split("\n")
        .map(line => line.trim())
        .filter(Boolean);

      const uniqueNewSubjects = lines
        .filter(name => !subjects.some(s => s.name === name))
        .map(name => ({ name, progress: 0, notes: "" }));

      setSubjects(prev => [...prev, ...uniqueNewSubjects]);
    };
    reader.readAsText(file);
  };

  const updateProgress = (index, value) => {
    setSubjects(prev => {
      const updated = [...prev];
      updated[index].progress = value;
      return updated;
    });
  };

  const updateNotes = (index, value) => {
    setSubjects(prev => {
      const updated = [...prev];
      updated[index].notes = value;
      return updated;
    });
  };

  const deleteSubject = (index) => {
    setSubjects(prev => prev.filter((_, i) => i !== index));
  };

  // REMOVE the local logout function. We will use the prop.
  // const logout = () => {
  //   localStorage.removeItem("user");
  //   window.location.href = "/";
  // };

  const hardcodedProblems = {
    Maths: [
      { question: "What is the derivative of x²?", answer: "2x" },
      { question: "Solve: ∫ x dx", answer: "x²/2 + C" }
    ],
    Physics: [
      { question: "State Newton's 2nd Law", answer: "F = ma" },
      { question: "Unit of Power?", answer: "Watt" }
    ],
    Chemistry: [
      { question: "What is the atomic number of Oxygen?", answer: "8" },
      { question: "HCl + NaOH → ?", answer: "NaCl + H₂O" }
    ],
    English: [
      { question: "What is a synonym for 'happy'?", answer: "Joyful" },
      { question: "Identify the verb: She runs fast.", answer: "runs" }
    ]
  };

  return (
    <div style={{ padding: "2rem", maxWidth: "600px", margin: "0 auto" }}>
      <h2>📊 Dashboard</h2>
      <p>Welcome, <strong>{userEmail}</strong></p>

      <input type="file" accept=".txt" onChange={handleUpload} />

      <div style={{ marginTop: "2rem" }}>
        {subjects.map((subject, index) => (
          <div key={index} style={{ marginBottom: "2rem", borderBottom: "1px solid #ccc", paddingBottom: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ flex: 1 }}>{subject.name}</span>
              <input
                type="range"
                min={0}
                max={100}
                value={subject.progress}
                onChange={(e) => updateProgress(index, parseInt(e.target.value))}
                style={{ margin: "0 1rem", flex: 2 }}
              />
              <span>{subject.progress}%</span>
              <button onClick={() => deleteSubject(index)} style={{ marginLeft: "1rem" }}>🗑️</button>
            </div>

            {/* Notes */}
            <textarea
              placeholder={`Notes for ${subject.name}`}
              value={subject.notes || ""}
              onChange={(e) => updateNotes(index, e.target.value)}
              rows={3}
              style={{ width: "100%", marginTop: "1rem", resize: "vertical" }}
            />

            {/* Practice Problems */}
            <button
              onClick={() =>
                setPracticeSubjectIndex(practiceSubjectIndex === index ? null : index)
              }
              style={{ marginTop: "1rem" }}
            >
              {practiceSubjectIndex === index ? "Hide Practice" : "Practice"}
            </button>

            {practiceSubjectIndex === index && (
              <div
                style={{
                  marginTop: "1rem",
                  background: "#f9f9f9",
                  padding: "1rem",
                  borderRadius: "5px",
                  color: "#000"
                }}
              >
                {hardcodedProblems[subject.name] ? (
                  hardcodedProblems[subject.name].map((problem, idx) => (
                    <div key={idx} style={{ marginBottom: "1rem" }}>
                      <strong>Q{idx + 1}: {problem.question}</strong>
                      <p><em>Ans:</em> {problem.answer}</p>
                    </div>
                  ))
                ) : (
                  <p>No problems available for this subject.</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Use the handleLogout prop */}
      <button onClick={handleLogout} style={{ marginTop: "2rem" }}>
        Logout
      </button>
    </div>
  );
}