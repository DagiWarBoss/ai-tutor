// src/AuthPage.jsx
import React, { useState } from "react";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
} from "firebase/auth";
import { auth } from "./firebase";
import { useNavigate } from "react-router-dom"; // <--- ADD THIS IMPORT

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [showResend, setShowResend] = useState(false);
  const [unverifiedUser, setUnverifiedUser] = useState(null);

  const navigate = useNavigate(); // <--- INITIALIZE useNavigate

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setShowResend(false);
    try {
      if (isLogin) {
        const userCred = await signInWithEmailAndPassword(auth, email, password);
        if (!userCred.user.emailVerified) {
          setUnverifiedUser(userCred.user);
          setShowResend(true);
          setMessage("❌ Email not verified. Please verify or resend email.");
          return;
        }
        localStorage.setItem("user", email);
        // localStorage.setItem("userToken", userCred.user.accessToken); // Consider storing token if needed for conditional rendering in App.jsx

        // *** FIX: Use navigate for redirection ***
        navigate("/"); // Redirect to the dashboard route (which is '/')
      } else {
        const userCred = await createUserWithEmailAndPassword(auth, email, password);
        await sendEmailVerification(userCred.user);
        setMessage("✅ Account created! Verification email sent.");
        setIsLogin(true);
      }
    } catch (error) {
      setMessage("❌ " + error.message);
    }
  };

  const resendVerification = async () => {
    if (unverifiedUser) {
      await sendEmailVerification(unverifiedUser);
      setMessage("📩 Verification email resent.");
    }
  };

  return (
    <div style={{ padding: "2rem", maxWidth: "400px", margin: "auto", color: '#fff' }}> {/* Added color: #fff for text visibility */}
      <h2>{isLogin ? "Login" : "Sign Up"}</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ display: "block", margin: "1rem 0", width: "100%", color: '#000' }} // Added color: #000 for input text
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ display: "block", margin: "1rem 0", width: "100%", color: '#000' }} // Added color: #000 for input text
        />
        <button type="submit" style={{ width: "100%", padding: "0.5rem" }}>
          {isLogin ? "Login" : "Sign Up"}
        </button>
      </form>

      {showResend && (
        <button onClick={resendVerification} style={{ marginTop: "1rem" }}>
          🔁 Resend Verification Email
        </button>
      )}

      <p style={{ marginTop: "1rem" }}>
        {isLogin ? "New user?" : "Already have an account?"}{" "}
        <button type="button" onClick={() => setIsLogin(!isLogin)}>
          {isLogin ? "Sign up" : "Login"}
        </button>
      </p>
      {message && <p>{message}</p>}
    </div>
  );
}