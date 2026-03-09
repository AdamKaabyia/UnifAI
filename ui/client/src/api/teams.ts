import backendApi from '@/http/backendClient';

export interface Team {
  team_id: string;
  name: string;
  created_by: string;
  members: string[];
  created_at: string;
  updated_at: string;
}

export interface TeamsListResponse {
  teams: Team[];
}

export async function createTeam(
  name: string,
  createdBy: string,
  members: string[]
): Promise<Team> {
  const { data } = await backendApi.post<Team>('/teams/team.create', {
    name,
    createdBy,
    members,
  });
  return data;
}

export async function listUserTeams(userId: string): Promise<Team[]> {
  const { data } = await backendApi.get<TeamsListResponse>('/teams/teams.list', {
    params: { userId },
  });
  return data.teams;
}

export async function getTeam(teamId: string): Promise<Team> {
  const { data } = await backendApi.get<Team>('/teams/team.get', {
    params: { teamId },
  });
  return data;
}

export async function updateTeam(
  teamId: string,
  updates: { name?: string; members?: string[] }
): Promise<Team> {
  const { data } = await backendApi.put<Team>('/teams/team.update', {
    teamId,
    ...updates,
  });
  return data;
}

export async function deleteTeam(teamId: string): Promise<void> {
  await backendApi.delete('/teams/team.delete', {
    params: { teamId },
  });
}
