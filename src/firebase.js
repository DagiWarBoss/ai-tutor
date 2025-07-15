// firebase.js
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getAnalytics } from "firebase/analytics";

// Your Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyCyPntKUMxjjd-et5l1F07tpI93525BRUY",
  authDomain: "ai-tutor-39ff9.firebaseapp.com",
  projectId: "ai-tutor-39ff9",
  storageBucket: "ai-tutor-39ff9.firebasestorage.app",
  messagingSenderId: "303541555607",
  appId: "1:303541555607:web:5d7d07a63ff5ed8e0434d2",
  measurementId: "G-4LT6577G8J"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
getAnalytics(app);