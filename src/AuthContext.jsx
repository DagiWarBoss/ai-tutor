// src/AuthContext.jsx

import React, { createContext, useContext, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase'; // Make sure your firebase.js is correctly set up

export const AuthContext = createContext(null); // <-- ADDED 'export' HERE

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

    // Removed conditional rendering for loading state from here.
    // The loading state is managed, but children are always rendered.
    // If you want a loading screen, it might be better placed in App.jsx or higher.

    return (
        <AuthContext.Provider value={{ currentUser, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);