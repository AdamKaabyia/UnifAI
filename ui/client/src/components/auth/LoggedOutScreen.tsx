import React from 'react';
import { FaSignInAlt } from 'react-icons/fa';

interface LoggedOutScreenProps {
  onLogin: () => void;
}

const LoggedOutScreen: React.FC<LoggedOutScreenProps> = ({ onLogin }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background-surface">
      <div className="flex flex-col items-center space-y-6 p-8 rounded-xl bg-background-card border border-gray-800 shadow-lg max-w-sm w-full mx-4">
        <div className="w-14 h-14 rounded-xl bg-gradient-to-r from-primary to-gray-500 flex items-center justify-center">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 12H7M17 12H21M12 3V7M12 17V21M5 19L8 16M16 8L19 5M19 19L16 16M5 5L8 8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div className="text-center space-y-2">
          <h2 className="text-xl font-heading font-bold text-white">You've been signed out</h2>
          <p className="text-sm text-gray-400">Your session has ended. Log in to continue using UnifAI.</p>
        </div>
        <button
          onClick={onLogin}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary hover:bg-opacity-80 text-white font-medium transition-colors"
        >
          <FaSignInAlt className="h-4 w-4" />
          Log in
        </button>
      </div>
    </div>
  );
};

export default LoggedOutScreen;
