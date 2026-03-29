import backendApi from '@/http/backendClient';

export interface DirectoryUser {
  user_id: string;
  username: string;
  display_name: string;
  email: string;
  title: string;
}

export async function getDirectoryStatus(): Promise<{ enabled: boolean }> {
  const { data } = await backendApi.get<{ enabled: boolean }>('/teams/directory.status');
  return data;
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
