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

export interface DirectoryUser {
  user_id: string;
  username: string;
  display_name: string;
  email: string;
  title: string;
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

export async function searchDirectoryUsers(
  query: string,
  limit: number = 10,
  accessToken?: string | null,
): Promise<DirectoryUser[]> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers['X-User-Token'] = accessToken;
  }
  const { data } = await backendApi.get<{ users: DirectoryUser[] }>(
    '/teams/directory.search_users',
    { params: { q: query, limit }, headers },
  );
  return data.users;
}
