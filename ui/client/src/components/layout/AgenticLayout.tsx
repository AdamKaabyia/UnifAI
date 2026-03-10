import React from "react";
import Sidebar from "./Sidebar";
import { useView } from "@/contexts/ViewContext";
import { Users, UserPlus } from "lucide-react";
import { motion } from "framer-motion";

interface AgenticLayoutProps {
  children: React.ReactNode;
}

export default function AgenticLayout({ children }: AgenticLayoutProps) {
  const { viewMode, teams, teamsLoading } = useView();

  const showNoTeams = viewMode === "team" && teams.length === 0 && !teamsLoading;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {showNoTeams ? <NoTeamsView /> : children}
      </div>
    </div>
  );
}

function NoTeamsView() {
  return (
    <div className="flex-1 flex items-center justify-center bg-background-dark">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-md px-6"
      >
        <div className="mx-auto w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <Users className="w-10 h-10 text-primary/60" />
        </div>
        <h2 className="text-xl font-heading font-semibold text-white mb-3">
          No Team Workspace Yet
        </h2>
        <p className="text-sm text-gray-400 leading-relaxed mb-2">
          To see a team workspace, join an existing team or create a new one.
          Use the team selector in the sidebar to get started.
        </p>
        <div className="flex items-center justify-center gap-2 mt-6 text-xs text-gray-600">
          <UserPlus className="w-3.5 h-3.5" />
          <span>Tip: Click <strong className="text-gray-400">Team</strong> in the sidebar, then <strong className="text-gray-400">Create a new team</strong></span>
        </div>
      </motion.div>
    </div>
  );
}
