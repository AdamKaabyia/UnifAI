import axios from "@/http/axiosAgentConfig";

export type TeamEditLockEntityKind = "resource" | "blueprint";

export interface TeamEditLockHolder {
  userId: string;
  displayName: string;
}

function isUnavailable(status: number | undefined): boolean {
  return status === 501;
}

export async function acquireTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
  displayName: string;
}): Promise<{ acquired: true } | { acquired: false; lockedBy: TeamEditLockHolder }> {
  try {
    const { data } = await axios.post<{
      acquired: boolean;
      lockedBy?: TeamEditLockHolder;
    }>("/collaboration/edit_lock.acquire", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
      displayName: params.displayName,
    });
    if (data.acquired) {
      return { acquired: true };
    }
    return {
      acquired: false,
      lockedBy: data.lockedBy ?? {
        userId: "?",
        displayName: "Another user",
      },
    };
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return { acquired: true };
    }
    throw e;
  }
}

export async function releaseTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
}): Promise<void> {
  try {
    await axios.post("/collaboration/edit_lock.release", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
    });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return;
    }
    throw e;
  }
}

export async function heartbeatTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
  displayName: string;
}): Promise<void> {
  try {
    await axios.post("/collaboration/edit_lock.heartbeat", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
      displayName: params.displayName,
    });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return;
    }
    console.warn("edit lock heartbeat failed", e);
  }
}

export async function fetchTeamEditLockStatuses(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityIds: string[];
}): Promise<Record<string, TeamEditLockHolder | null>> {
  if (params.entityIds.length === 0) {
    return {};
  }
  try {
    const { data } = await axios.post<{ locks: Record<string, TeamEditLockHolder | null> }>(
      "/collaboration/edit_lock.statuses",
      {
        teamId: params.teamId,
        entityKind: params.entityKind,
        entityIds: params.entityIds,
      },
    );
    return data.locks ?? {};
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return {};
    }
    console.warn("edit lock statuses failed", e);
    return {};
  }
}
