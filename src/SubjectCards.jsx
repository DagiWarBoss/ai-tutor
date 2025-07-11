import React from "react";

const dummySubjects = [
  { name: "Mathematics", progress: 30 },
  { name: "Physics", progress: 50 },
  { name: "Chemistry", progress: 20 },
];

export default function SubjectCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
      {dummySubjects.map((subject, index) => (
        <div
          key={index}
          className="p-4 border rounded-xl shadow bg-white flex flex-col"
        >
          <h4 className="text-md font-semibold mb-2">{subject.name}</h4>
          <div className="h-2 w-full bg-gray-200 rounded-full mb-1">
            <div
              className="h-2 bg-green-500 rounded-full"
              style={{ width: `${subject.progress}%` }}
            ></div>
          </div>
          <p className="text-sm">{subject.progress}% completed</p>
        </div>
      ))}
    </div>
  );
}

function QuickTestButton({ subject }) {
  const generateTest = () => {
    // Read your existing syllabus file
    const topics = require(`./${subject}.txt`).split('\n');
    
    // Create 3 random questions (real utility)
    const questions = topics.slice(0, 3).map(topic => ({
      question: `Explain ${topic} in one sentence.`,
      options: ["Definition", "Formula", "Example", "None"],
      answer: 0
    }));
    
    localStorage.setItem(`${subject}-quiz`, JSON.stringify(questions));
    window.location.href = `/quiz/${subject}`;
  };

  return <button onClick={generateTest}>Quick Test</button>;
}