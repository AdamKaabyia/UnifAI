import React, { useEffect } from "react";
import { Route, Switch, useRoute } from "wouter";
import RagOverview from "@/pages/RagOverview";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import JiraIntegration from "@/pages/JiraIntegration";
import AgenticWorkflows from "@/pages/AgenticWorkflows";
import AgentRepository from "@/pages/AgentRepository";
import AgenticChats from "@/pages/AgenticChats";
import AgenticTemplates from "@/pages/AgenticTemplates";
import GetToKnow from "@/pages/GetToKnow";
import Analytics from "@/pages/Analytics";
import NotFound from "@/pages/not-found";
import Login from "@/pages/Login";
import { ProjectProvider } from '@/contexts/ProjectContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SharedProvider } from '@/contexts/SharedContext';
import DocumentsPage from "./features/docs/DocumentsPage";
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AgenticAIProvider } from '@/contexts/AgenticAIContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import TermsApproval from '@/components/auth/TermsApproval';
import SlackIntegration from "./features/slack/SlackIntegration";
import SlackAddSourcePage from "./features/slack/SlackAddSourcePage";
import GuidesPage from "./components/guides/GuidesPage";
import PublicChat from "./components/agentic-ai/chat/PublicChat";

// Routes component that conditionally wraps agentic routes with the shared provider
function AppRoutes() {
  const [isChat] = useRoute("/chat/:token");
  const [isAgenticOverview] = useRoute("/agentic-overview");
  const [isAgenticAI] = useRoute("/agentic-ai");
  const [isInventory] = useRoute("/inventory");
  const [isAgenticChats] = useRoute("/agentic-chats");
  const [isTemplates] = useRoute("/templates");

  const isAgenticRoute = isChat || isAgenticOverview || isAgenticAI || isInventory || isAgenticChats || isTemplates;

  if (isAgenticRoute) {
    return (
      <AgenticAIProvider>
        <Switch>
          <Route path="/agentic-overview" component={AgenticOverview} />
          <Route path="/agentic-ai" component={AgenticWorkflows} />
          <Route path="/inventory" component={AgentRepository} />
          <Route path="/agentic-chats" component={AgenticChats} />
          <Route path="/templates" component={AgenticTemplates} />
          <Route path="/chat/:token" component={PublicChat} />
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
      <Route path="/analytics" component={Analytics} />
      <Route component={NotFound} />
    </Switch>
  );
}

/** /login outside ProtectedRoute; use full navigation (no wouter setLocation) to match app routing convention. */
function LoginRouteContent() {
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      window.location.replace('/');
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0D1117]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600" />
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  return <Login />;
}

function AppContent() {
  return (
    <Switch>
      <Route path="/login">
        <LoginRouteContent />
      </Route>
      <Route>
        <ProtectedRoute>
          <TermsApproval>
            <AppRoutes />
          </TermsApproval>
        </ProtectedRoute>
      </Route>
    </Switch>
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

