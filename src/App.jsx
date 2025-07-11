// src/App.jsx

// Import your existing TestAI component.
// The path is now directly "./TestAI" because TestAI.jsx is in the 'src' folder.
import TestAI from "./TestAI"; 

// Import the new ProblemGenerator component.
// This assumes ProblemGenerator.jsx is also directly in the 'src' folder.
import ProblemGenerator from "./ProblemGenerator"; 

// Note: The createRoot and StrictMode setup belongs in main.jsx, not here.
// This App.jsx file should only define and export the App component.

function App() {
  // If you are using React Router for navigation, your routes would typically
  // be defined here or in a parent component that wraps App.
  // For example, if you want ProblemGenerator on a specific route:
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