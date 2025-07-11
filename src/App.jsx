// src/App.jsx

// Import your existing TestAI component
import TestAI from "./components/TestAI";

// Import the new ProblemGenerator component
// Ensure ProblemGenerator.jsx is in the same 'src' directory
import ProblemGenerator from "./ProblemGenerator";

// Note: The createRoot and StrictMode setup belongs in main.jsx, not here.
// This App.jsx file should only define and export the App component.

function App() {
  // If you are using React Router for navigation, your routes would typically
  // be defined here or in a parent component that wraps App.
  // For example:
  // import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
  // return (
  //   <Router>
  //     <Routes>
  //       <Route path="/" element={<div><TestAI /><ProblemGenerator /></div>} />
  //       <Route path="/quiz/:subject" element={<Quiz />} />
  //       {/* Add other routes as needed */}
  //     </Routes>
  //   </Router>
  // );

  return (
    <div>
      {/* Render your existing TestAI component */}
      <TestAI />

      {/* Optional: Add a horizontal rule for visual separation */}
      <hr style={{ margin: '50px 0', borderColor: '#eee' }} />
      
      {/* Render the ProblemGenerator component */}
      <ProblemGenerator />
    </div>
  );
}

export default App;