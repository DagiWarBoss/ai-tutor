import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Import your existing TestAI component
import TestAI from "./components/TestAI";

// --- NEW: Import the ProblemGenerator component ---
import ProblemGenerator from "./ProblemGenerator"; // Assuming ProblemGenerator.jsx is in the same 'src' directory

function App() {
  // Your React Router setup would typically look something like this in a higher-level component,
  // or wrap your main content if you're using BrowserRouter/HashRouter.
  // <Route path="/quiz/:subject" element={<Quiz />} />

  return (
    <div>
      {/* Render your existing TestAI component */}
      <TestAI />

      {/* --- NEW: Render the ProblemGenerator component here --- */}
      <hr style={{ margin: '50px 0' }} /> {/* Optional: add a separator */}
      <ProblemGenerator />
    </div>
  );
}

export default App;