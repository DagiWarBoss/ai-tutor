// src/ProtectedRoute.jsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

const ProtectedRoute = ({ children }) => {
  const { currentUser, loading } = useAuth();

  console.log("ProtectedRoute - currentUser:", currentUser);
  console.log("ProtectedRoute - loading:", loading);

  if (loading) {
    return <div>Loading authentication...</div>;
  }

  if (!currentUser) {
    console.log("ProtectedRoute - Redirecting to /auth because currentUser is null.");
    return <Navigate to="/auth" replace />;
  }

  return children;
};

export default ProtectedRoute;