import React from "react";
import Sidebar from "./Sidebar";

interface AgenticLayoutProps {
  children: React.ReactNode;
}

export default function AgenticLayout({ children }: AgenticLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
