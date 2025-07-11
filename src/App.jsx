// src/App.jsx

// REMOVE OR COMMENT OUT THIS LINE IF IT'S STILL THERE:
// import TestAI from "./TestAI";

// Import the new ProblemGenerator component.
// This assumes ProblemGenerator.jsx is directly in the 'src' folder.
import ProblemGenerator from "./ProblemGenerator";

function App() {
  return (
    <div>
      {/* REMOVE OR COMMENT OUT THIS LINE IF IT'S STILL THERE: */}
      {/* <TestAI /> */}

      {/* Optional: Add a horizontal rule for visual separation */}
      <hr style={{ margin: '50px 0', borderColor: '#eee' }} />

      {/* Render the ProblemGenerator component */}
      <ProblemGenerator />
    </div>
  );
}

export default App;