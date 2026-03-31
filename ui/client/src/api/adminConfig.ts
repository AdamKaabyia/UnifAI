import { backendApi } from '@/http/backendClient';

// ─────────────────────────────────────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────────────────────────────────────

export interface FieldValue {
  key: string;
  label: string;
  field_type: string;
  description: string;
  default: unknown;
  placeholder: string;
  value: unknown;
}

export interface SectionValue {
  key: string;
  title: string;
  description: string;
  fields: FieldValue[];
  on_update_action: string | null;
  updated_at: string | null;
}

export interface CategoryValue {
  key: string;
  title: string;
  description: string;
  sections: SectionValue[];
}

export interface AdminConfigResponse {
  categories: CategoryValue[];
}

export interface UpdateSectionResponse {
  status: string;
  on_update_action: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
//  API calls
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch the full admin config template merged with stored values.
 * Pass username so the backend can enforce admin access when needed.
 */
export async function getAdminConfig(username?: string): Promise<AdminConfigResponse> {
  const headers = username ? { 'X-Username': username } : undefined;
  const response = await backendApi.get('/admin_config/config.get', { headers });
  return response.data;
}

/**
 * Update a single config section's values.
 * Pass username so the backend can enforce admin access.
 */
export async function updateAdminConfigSection(
  sectionKey: string,
  values: Record<string, unknown>,
  username?: string,
): Promise<UpdateSectionResponse> {
  const headers = username ? { 'X-Username': username } : undefined;
  const response = await backendApi.put(
    '/admin_config/config.section.update',
    { sectionKey, values },
    { headers },
  );
  return response.data;
}

/**
 * Check whether the given username has admin access.
 */
export async function checkAdminAccess(
  username: string,
): Promise<{ is_admin: boolean }> {
  const response = await backendApi.get('/admin_config/access.check', {
    params: { username },
  });
  return response.data;
}
