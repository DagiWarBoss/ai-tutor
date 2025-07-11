// src/AuthPage.jsx
import React, { useState } from "react";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  getAuth, // Import getAuth to access current user for re-check
} from "firebase/auth";
import { auth } from "./firebase";
import { useNavigate } from "react-router-dom";
import { useAuth } from './AuthContext'; // Import useAuth to check current user

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [showResend, setShowResend] = useState(false);
  const [unverifiedUser, setUnverifiedUser] = useState(null); // Keep this for resending

  const navigate = useNavigate();
  const { currentUser } = useAuth(); // Get currentUser from context

  // If user is already logged in, redirect them away from AuthPage
  // This helps prevent them from seeing the login form if already authenticated
  React.useEffect(() => {
    if (currentUser) {
      navigate('/'); // Redirect to dashboard if already logged in
    }
  }, [currentUser, navigate]);


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
          return; // Stop here if not verified
        }
        // If email is verified, navigate to dashboard
        // localStorage.setItem("user", email); // AuthContext will handle this
        navigate("/");
      } else {
        const userCred = await createUserWithEmailAndPassword(auth, email, password);
        await sendEmailVerification(userCred.user);
        setMessage("✅ Account created! Verification email sent. Please log in after verification.");
        setIsLogin(true); // Switch to login form after signup
        setEmail(""); // Clear form
        setPassword("");
      }
    } catch (error) {
      // Firebase error codes can be handled here for friendlier messages
      if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password') {
        setMessage('❌ Invalid email or password.');
      } else if (error.code === 'auth/email-already-in-use') {
        setMessage('❌ Email already in use. Try logging in.');
      } else {
        setMessage("❌ " + error.message);
      }
    }
  };

  const resendVerification = async () => {
    if (unverifiedUser) {
      try {
        await sendEmailVerification(unverifiedUser);
        setMessage("📩 Verification email resent. Check your inbox.");
      } catch (error) {
        setMessage("❌ Failed to resend verification email: " + error.message);
      }
    }
  };

  // If currentUser exists, we're navigating away due to useEffect, so don't render form
  if (currentUser) {
    return null; // Or a simple loading/redirect message
  }

  return (
    <div style={{ padding: "2rem", maxWidth: "400px", margin: "auto", color: '#fff' }}>
      <h2>{isLogin ? "Login" : "Sign Up"}</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ display: "block", margin: "1rem 0", width: "100%", color: '#000' }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ display: "block", margin: "1rem 0", width: "100%", color: '#000' }}
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