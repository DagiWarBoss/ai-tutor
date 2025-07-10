import { motion } from "framer-motion";

export default function Hero() {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="hero-gradient-bg text-white p-12 text-center"
    >
      <h1 className="text-5xl font-bold mb-4">Your Personal NCERT AI Tutor</h1>
      <p className="text-xl mb-8">Ask anything from Class 11-12 Physics, Chemistry, Math</p>
      <button className="glow-button px-8 py-3 rounded-full">
        Try Now →
      </button>
    </motion.div>
  );
}