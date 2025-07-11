// src/ProtectedRoute.jsx

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

const ProtectedRoute = ({ children }) => {
  const { currentUser, loading } = useAuth();

  if (loading) {
    // You can render a loading spinner here
    return <div>Loading authentication...</div>;
  }

  if (!currentUser) {
    // User is not logged in, redirect to login page
    return <Navigate to="/auth" replace />;
  }

  return children; // User is logged in, render the child component
};

export default ProtectedRoute;