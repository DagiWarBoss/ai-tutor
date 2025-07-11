// src/AuthContext.js

import React, { createContext, useContext, useEffect, useState } from 'react'; // <--- ADD useContext here
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase'; // Make sure your firebase.js is correctly set up

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, user => {
      setCurrentUser(user);
      setLoading(false);

      // Optionally, update localStorage 'user' and 'userToken' here
      if (user) {
        localStorage.setItem('user', user.email);
        // You might want to store idToken for API calls, but be mindful of expiry
        user.getIdToken().then(token => {
          localStorage.setItem('userToken', token);
        });
      } else {
        localStorage.removeItem('user');
        localStorage.removeItem('userToken');
      }
    });

    return unsubscribe; // Cleanup subscription on unmount
  }, []);

  return (
    <AuthContext.Provider value={{ currentUser, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);