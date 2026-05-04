import { api as identityApi } from '@/http/authClient';
import agentApi from '@/http/axiosAgentConfig';

export type TeamMemberType = 'user' | 'group';

export interface TeamMember {
  type: TeamMemberType;
  id: string;
  display_name: string;
  group_members?: string[];
}

/**
 * Return the effective member count for a team.  Prefers the
 * Identity-computed ``effective_member_count`` when available, otherwise
 * falls back to a client-side calculation from ``group_members``.
 */
export function getEffectiveMemberCount(
  members: TeamMember[],
  backendCount?: number,
): number {
  if (typeof backendCount === 'number') return backendCount;
  const userIds = new Set<string>();
  for (const m of members) {
    if (m.type === 'user') {
      userIds.add(m.id);
    } else if (m.type === 'group' && m.group_members) {
      for (const uid of m.group_members) {
        userIds.add(uid);
      }
    }
  }
  return userIds.size;
}

export interface Team {
  team_id: string;
  name: string;
  created_by: string;
  members: TeamMember[];
  created_at: string;
  updated_at: string;
  effective_member_count?: number;
}

export interface TeamsListResponse {
  teams: Team[];
}

export async function createTeam(
  name: string,
  createdBy: string,
  members: TeamMember[]
): Promise<Team> {
  const { data } = await identityApi.post<Team>('/teams/team.create', {
    name,
    createdBy,
    members,
  });
  return data;
}

export async function listUserTeams(
  userId: string,
  groupIds?: string[],
): Promise<Team[]> {
  const params: Record<string, string> = { userId };
  if (groupIds && groupIds.length > 0) {
    params.groupIds = groupIds.join(',');
  }
  const { data } = await identityApi.get<TeamsListResponse>('/teams/teams.list', {
    params,
  });
  return data.teams;
}

export async function getTeam(teamId: string): Promise<Team> {
  const { data } = await identityApi.get<Team>('/teams/team.get', {
    params: { teamId },
  });
  return data;
}

export async function updateTeam(
  teamId: string,
  updates: { name?: string; members?: TeamMember[] }
): Promise<Team> {
  const { data } = await identityApi.put<Team>('/teams/team.update', {
    teamId,
    ...updates,
  });
  return data;
}

/**
 * Clean up all multi-agent data (resources, blueprints, sessions) owned by a
 * team identity, then delete the team record in Identity (Mongo).
 */
export async function deleteTeam(teamId: string, requestedBy: string): Promise<void> {
  await agentApi.delete('/workspace/workspace.cleanup', {
    data: { identityType: 'team', identityId: teamId },
  });

  await identityApi.delete('/teams/team.delete', {
    params: { teamId, requestedBy },
  });
}
