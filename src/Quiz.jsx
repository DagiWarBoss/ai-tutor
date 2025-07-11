export default function Quiz() {
  const { subject } = useParams();
  const [questions, setQuestions] = useState([]);
  
  useEffect(() => {
    setQuestions(JSON.parse(localStorage.getItem(`${subject}-quiz`)));
  }, [subject]);

  return (
    <div>
      {questions.map((q, i) => (
        <div key={i}>
          <h4>{q.question}</h4>
          {q.options.map((opt, j) => (
            <button key={j} onClick={() => alert(j === q.answer ? "Correct!" : "Wrong")}>
              {opt}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}