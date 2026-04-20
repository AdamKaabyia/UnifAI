import { api } from '@/http/authClient';
import React, { createContext, useContext, useCallback, useEffect, useState, ReactNode } from 'react';
import { loadAnalytics } from '@/components/shared/LoadAnalytics';

export interface User {
  username: string;
  email: string;
  name: string;
  sub: string;
  token_expires_at: number;
  is_admin?: boolean;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isLoggedOut: boolean;
  login: () => void;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoggedOut, setIsLoggedOut] = useState(() => {
    return localStorage.getItem('unifai_logged_out') === 'true';
  });
  // Load analytics after authentication
  loadAnalytics(isAuthenticated, user);

  // Sync logout state across tabs via the storage event
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key !== 'unifai_logged_out') return;
      const loggedOut = e.newValue === 'true';
      setIsLoggedOut(loggedOut);
      if (loggedOut) {
        setUser(null);
        setIsAuthenticated(false);
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const checkAuthStatus = useCallback(async () => {
    try {
      const response = await api.get('/auth/user');
      if (response.data.authenticated && response.data.user) {
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(() => {
    // If coming back from logout, force Keycloak to show the login form
    // instead of silently re-authenticating via Kerberos
    const forcePrompt = isLoggedOut;

    setIsLoggedOut(false);
    localStorage.removeItem('unifai_logged_out');

    const originalUrl = window.location.pathname + window.location.search;
    const stateData = { originalUrl: originalUrl || '/', forcePrompt };
    const encodedState = btoa(JSON.stringify(stateData));

    const promptParam = forcePrompt ? '&prompt=login' : '';
    window.location.href = `${api.defaults.baseURL}/auth/login?state=${encodeURIComponent(encodedState)}${promptParam}`;
  }, [isLoggedOut]);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoggedOut(true);
      localStorage.setItem('unifai_logged_out', 'true');
      window.location.href = '/login';
    }
  }, []);

  // Handle authentication callback from URL params on mount
  useEffect(() => {
    if (isLoggedOut) {
      setIsLoading(false);
      return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('auth');
    const stateParam = urlParams.get('state');

    if (authStatus === 'success') {
      let originalUrl = '/';
      if (stateParam) {
        try {
          const decodedState = JSON.parse(atob(decodeURIComponent(stateParam)));
          originalUrl = decodedState.originalUrl || '/';
        } catch (error) {
          console.error('Failed to decode state parameter:', error);
        }
      }

      // Remove auth params from URL (normalize pathname to avoid protocol-relative URL issues)
      const cleanPath = window.location.pathname.replace(/^\/+/, '/') || '/';
      window.history.replaceState({}, document.title, cleanPath);

      // Check auth status after successful login
      checkAuthStatus().then(() => {
        // Restore the original URL after authentication is confirmed
        if (originalUrl && originalUrl !== '/') {
          window.location.replace(originalUrl);
        }
      });
    } else if (authStatus === 'error') {
      // On error, try to preserve the original URL from state and retry login
      if (stateParam) {
        try {
          const decodedState = JSON.parse(atob(decodeURIComponent(stateParam)));
          const originalUrl = decodedState.originalUrl || '/';
          const retryForcePrompt = decodedState.forcePrompt ?? false;
          console.log('Authentication failed, retrying with preserved URL:', originalUrl);

          // Re-encode state and retry login
          const stateData = { originalUrl, forcePrompt: retryForcePrompt };
          const encodedState = btoa(JSON.stringify(stateData));
          const promptParam = retryForcePrompt ? '&prompt=login' : '';
          window.location.href = `${api.defaults.baseURL}/auth/login?state=${encodeURIComponent(encodedState)}${promptParam}`;
          return; // Don't set loading to false yet, we're redirecting
        } catch (error) {
          console.error('Failed to decode state parameter on error:', error);
        }
      }
      // Remove auth params from URL (normalize pathname to avoid protocol-relative URL issues)
      const cleanPath = window.location.pathname.replace(/^\/+/, '/') || '/';
      window.history.replaceState({}, document.title, cleanPath);
      setIsLoading(false);
      console.error('Authentication failed');
    } else {
      // Initial load - check if user is already authenticated
      checkAuthStatus();
    }
  }, [isLoggedOut, checkAuthStatus]);

  // Periodically refresh access token before it expires
  useEffect(() => {
    if (!isAuthenticated || !user || isLoggedOut) return;

    const checkTokenExpiration = () => {
      const timeUntilExpiry = user.token_expires_at - Date.now() / 1000;
      if (timeUntilExpiry < 60) {
        api.post('/auth/refresh')
          .then(() => checkAuthStatus())
          .catch((error) => {
            console.error('Token refresh failed:', error);
            logout();
          });
      }
    };

    const interval = setInterval(checkTokenExpiration, 600000);
    checkTokenExpiration();

    return () => clearInterval(interval);
  }, [isAuthenticated, user, isLoggedOut, checkAuthStatus, logout]);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    isLoggedOut,
    login,
    logout,
    checkAuthStatus,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
