// frontend/src/AppContentContext.jsx

import React, { createContext, useState } from 'react';

// Create the context
export const AppContentContext = createContext(null);

// Create the context provider component
export const AppContentProvider = ({ children }) => {
    const [lastUploadedSyllabusId, setLastUploadedSyllabusId] = useState(null);

    // This value object will be provided to consumers of the context
    const contextValue = {
        lastUploadedSyllabusId,
        setLastUploadedSyllabusId,
    };

    return (
        <AppContentContext.Provider value={contextValue}>
            {children}
        </AppContentContext.Provider>
    );
};