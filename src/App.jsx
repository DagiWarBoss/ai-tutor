// src/App.jsx

// REMOVE or COMMENT OUT THIS LINE:
// import TestAI from "./TestAI";

// Import the new ProblemGenerator component.
import ProblemGenerator from "./ProblemGenerator";

function App() {
  return (
    <div>
      {/* REMOVE or COMMENT OUT THIS LINE: */}
      {/* <TestAI /> */}

      <hr style={{ margin: '50px 0', borderColor: '#eee' }} />

      <ProblemGenerator />
    </div>
  );
}

export default App;