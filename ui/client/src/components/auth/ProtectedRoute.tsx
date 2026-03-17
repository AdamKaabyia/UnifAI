import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/auth/LoadingSpinner';
import LoggedOutScreen from '@/components/auth/LoggedOutScreen';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, isLoggedOut, login } = useAuth();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return <LoadingSpinner />;
  }

  // User explicitly logged out — show logged-out screen instead of auto-redirecting
  if (isLoggedOut && !isAuthenticated) {
    return <LoggedOutScreen onLogin={login} />;
  }

  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    login();
    return <LoadingSpinner message="Redirecting to login..." />;
  }

  // If authenticated, render the protected content
  return <>{children}</>;
};

export default ProtectedRoute;