import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { listUserTeams, Team, TeamMember } from "@/api/teams";

export type ViewMode = "private" | "team";

export interface TeamInfo {
  id: string;
  name: string;
  members: TeamMember[];
  created_by: string;
  effective_member_count?: number;
}

export interface ViewContextType {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  selectedTeam: TeamInfo | null;
  setSelectedTeam: (team: TeamInfo | null) => void;
  teams: TeamInfo[];
  refreshTeams: () => Promise<void>;
  teamsLoading: boolean;
  userGroups: string[];
}

function toTeamInfo(t: Team): TeamInfo {
  return {
    id: t.team_id,
    name: t.name,
    members: t.members,
    created_by: t.created_by,
    effective_member_count: t.effective_member_count,
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
  userGroups: [],
};

const ViewContext = createContext<ViewContextType>(defaultViewContext);

export function ViewProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>("private");
  const [selectedTeam, setSelectedTeam] = useState<TeamInfo | null>(null);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [userGroups, setUserGroups] = useState<string[]>([]);

  const selectedTeamRef = useRef(selectedTeam);
  selectedTeamRef.current = selectedTeam;

  const refreshTeams = useCallback(async () => {
    if (!user?.username) return;
    setTeamsLoading(true);
    try {
      // Fetch user's ROVER groups for dynamic team membership
      let groups: string[] = [];
      try {
        const { api } = await import('@/http/authClient');
        const res = await api.get<{ groups: string[] }>('/auth/user/groups');
        groups = res.data.groups || [];
        setUserGroups(groups);
      } catch {
        // Groups endpoint may not be available; fall back gracefully
      }

      const fetched = await listUserTeams(user.username, groups.length > 0 ? groups : undefined);
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
        userGroups,
      }}
    >
      {children}
    </ViewContext.Provider>
  );
}

export function useView() {
  return useContext(ViewContext);
}
