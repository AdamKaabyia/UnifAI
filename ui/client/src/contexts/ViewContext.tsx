import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { listUserTeams, Team } from "@/api/teams";

export type ViewMode = "private" | "team";

export interface TeamInfo {
  id: string;
  name: string;
  members: string[];
  created_by: string;
}

export interface ViewContextType {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  selectedTeam: TeamInfo | null;
  setSelectedTeam: (team: TeamInfo | null) => void;
  teams: TeamInfo[];
  refreshTeams: () => Promise<void>;
  teamsLoading: boolean;
}

function toTeamInfo(t: Team): TeamInfo {
  return {
    id: t.team_id,
    name: t.name,
    members: t.members,
    created_by: t.created_by,
  };
}

const defaultViewContext: ViewContextType = {
  viewMode: "private",
  setViewMode: () => {},
  selectedTeam: null,
  setSelectedTeam: () => {},
  teams: [],
  refreshTeams: async () => {},
  teamsLoading: false,
};

const ViewContext = createContext<ViewContextType>(defaultViewContext);

export function ViewProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>("private");
  const [selectedTeam, setSelectedTeam] = useState<TeamInfo | null>(null);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);

  const selectedTeamRef = useRef(selectedTeam);
  selectedTeamRef.current = selectedTeam;

  const refreshTeams = useCallback(async () => {
    if (!user?.username) return;
    setTeamsLoading(true);
    try {
      const fetched = await listUserTeams(user.username);
      const mapped = fetched.map(toTeamInfo);
      setTeams(mapped);
      const current = selectedTeamRef.current;
      if (current) {
        const updated = mapped.find((t) => t.id === current.id);
        if (updated) {
          setSelectedTeam(updated);
        } else if (mapped.length > 0) {
          setSelectedTeam(mapped[0]);
        } else {
          setSelectedTeam(null);
        }
      } else if (mapped.length > 0) {
        setSelectedTeam(mapped[0]);
      }
    } catch (err) {
      console.error("Failed to fetch teams:", err);
    } finally {
      setTeamsLoading(false);
    }
  }, [user?.username]);

  useEffect(() => {
    refreshTeams();
  }, [refreshTeams]);

  return (
    <ViewContext.Provider
      value={{
        viewMode,
        setViewMode,
        selectedTeam,
        setSelectedTeam,
        teams,
        refreshTeams,
        teamsLoading,
      }}
    >
      {children}
    </ViewContext.Provider>
  );
}

export function useView() {
  return useContext(ViewContext);
}
