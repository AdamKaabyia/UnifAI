import React, { useEffect } from "react";
import { Route, Switch, useLocation } from "wouter";
import RagOverview from "@/pages/RagOverview";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import JiraIntegration from "@/pages/JiraIntegration";
import AgenticWorkflows from "@/pages/AgenticWorkflows";
import AgentRepository from "@/pages/AgentRepository";
import AgenticChats from "@/pages/AgenticChats";
import GetToKnow from "@/pages/GetToKnow";
import NotFound from "@/pages/not-found";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Settings from "@/pages/Settings";
import { ProjectProvider } from '@/contexts/ProjectContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SharedProvider } from '@/contexts/SharedContext';
import DocumentsPage from "./features/docs/DocumentsPage";
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AgenticAIProvider } from '@/contexts/AgenticAIContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import SlackIntegration from "./features/slack/SlackIntegration";
import SlackAddSourcePage from "./features/slack/SlackAddSourcePage";
import GuidesPage from "./components/guides/GuidesPage";

// Paths that require AgenticAIProvider
const AGENTIC_PATHS = ['/agentic-overview', '/agentic-ai', '/inventory', '/agentic-chats'];

// Routes component that conditionally wraps agentic routes with the shared provider
function AppRoutes() {
  const [location] = useLocation();
  
  const isAgenticRoute = AGENTIC_PATHS.some(path => location === path);

  if (isAgenticRoute) {
    return (
      <AgenticAIProvider>
        <Switch>
          <Route path="/agentic-overview" component={AgenticOverview} />
          <Route path="/agentic-ai" component={AgenticWorkflows} />
          <Route path="/inventory" component={AgentRepository} />
          <Route path="/agentic-chats" component={AgenticChats} />
        </Switch>
      </AgenticAIProvider>
    );
  }

  return (
    <Switch>
      <Route path="/" component={GetToKnow} />
      <Route path="/rag-overview" component={RagOverview} />
      <Route path="/jira" component={JiraIntegration} />
      <Route path="/slack" component={SlackIntegration} />
      <Route path="/documents" component={DocumentsPage} />
      <Route path="/slack/add-source" component={SlackAddSourcePage} />
      <Route path="/get-to-know" component={GetToKnow} />
      <Route path="/configuration" component={Configuration} />
      <Route path="/guides" component={GuidesPage} />
      <Route path="/settings" component={Settings} />
      <Route component={NotFound} />
    </Switch>
  );
}

// Component to redirect authenticated users away from auth pages
const AuthRoute: React.FC<{ component: React.ComponentType }> = ({ component: Component }) => {
  const { isAuthenticated, isLoading } = useAuth();
  
  // If authenticated and not loading, redirect to home
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      window.location.href = '/';
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-[#0D1117]">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
    </div>;
  }

  if (isAuthenticated) {
    return null;
  }

  return <Component />;
};

// Public auth paths that don't need ProtectedRoute
const PUBLIC_AUTH_PATHS = ['/login', '/signup'];

function AppContent() {
  const [location] = useLocation();
  
  // Check if current path is a public auth route
  const isPublicAuthRoute = PUBLIC_AUTH_PATHS.includes(location);
  
  if (isPublicAuthRoute) {
    return (
      <Switch>
        <Route path="/login">
          <AuthRoute component={Login} />
        </Route>
        <Route path="/signup">
          <AuthRoute component={Signup} />
        </Route>
      </Switch>
    );
  }
  
  return (
    <ProtectedRoute>
      <AppRoutes />
    </ProtectedRoute>
  );
}

function App() {
  // Set document title
  useEffect(() => {
    document.title = "UnifAI";
  }, []);

  return (
    <ThemeProvider>
      <AuthProvider>
        <SharedProvider>
          <ProjectProvider>
            <NotificationProvider>
              <AppContent />
            </NotificationProvider>
          </ProjectProvider>
        </SharedProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;

