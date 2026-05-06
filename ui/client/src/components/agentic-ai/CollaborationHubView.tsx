import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "@/http/axiosAgentConfig";
import { fetchResolvedBlueprint } from "@/api/blueprints";
import { useStreamingData } from "./StreamingDataContext";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import { ChatSession, ChatMessage, ChatSessionData } from "@/types/session";
import { transformSessionData, sortSessionsByTimestamp } from "@/utils/sessionHelpers";
import { useSessionManagement } from "@/hooks/use-session-management";
import { SessionPayload } from "./ExecutionTab";
import { useBlueprintValidation } from "@/hooks/use-blueprint-validation";
import { useSessionStream } from "@/hooks/use-session-stream";
import { FlowObject } from "./graphs/interfaces";
import {
  CollaborationHubSessionSidebar,
  CollaborationHubMainColumn,
  CollaborationHubRightPanel,
  CollaborationHubModals,
} from "./collaborationHubPanels";

import { MemberDisplay, buildMemberDisplay } from "@/utils/memberDisplay";

const COLLAB_POLL_INTERVAL = 3000;
const COLLAB_HEARTBEAT_INTERVAL = 30000;

interface CollaborationHubViewProps {
  runId: string | null;
  teamMembers: MemberDisplay[];
  teamName: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function CollaborationHubView({ runId, teamMembers, teamName }: CollaborationHubViewProps) {
  // Session state
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [currentSessionMessages, setCurrentSessionMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLiveRequest, setIsLiveRequest] = useState(false);
  const [globalScope] = useState<"public" | "private">("public");
  const [isSharingDisabled, setIsSharingDisabled] = useState(false);
  const [blueprintSpecCache, setBlueprintSpecCache] = useState<Map<string, any>>(new Map());

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Add flow modal
  const [showAddFlowModal, setShowAddFlowModal] = useState(false);
  const [selectedFlowForModal, setSelectedFlowForModal] = useState<FlowObject | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  // Per-session participant tracking from backend (sessionId -> usernames)
  const [sessionParticipants, setSessionParticipants] = useState<Record<string, string[]>>({});
  // Whether a remote user is executing (detected via session status poll)
  const [isSessionBusy, setIsSessionBusy] = useState(false);
  // Typing indicators from other users
  const [typingUsers, setTypingUsers] = useState<string[]>([]);

  const { nodeListRef, clearStream } = useStreamingData();
  const { user } = useAuth();
  const { viewMode, selectedTeam } = useView();
  const isTeam = viewMode === "team" && !!selectedTeam;
  const contextUserId = isTeam ? selectedTeam!.id : (user?.username || "default");
  const identityType = isTeam ? "team" : "user";

  const sessionSelectRequestId = useRef(0);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const sessionListPollCounterRef = useRef(0);
  const contextUserIdRef = useRef(contextUserId);
  const identityTypeRef = useRef(identityType);
  const joinedSessionRef = useRef<string | null>(null);
  const selectedSessionRef = useRef<ChatSession | null>(null);
  const isLiveRequestRef = useRef(false);
  const wasSessionBusyRef = useRef(false);
  const streamCompleteResolverRef = useRef<(() => void) | null>(null);

  const {
    isValidating: isValidatingBlueprint,
    isValid: isBlueprintValid,
    validateBlueprint: validateSelectedBlueprint,
    validationResults: blueprintValidationResults,
  } = useBlueprintValidation({ showToastOnFailure: true });

  const { loadSessionMessages } = useSessionManagement();

  // Ref for updateNodeList so the session stream hook can use it before it's defined
  const updateNodeListRef = useRef<((chunkData: any) => void) | null>(null);

  // Remote streaming: subscribe to Redis stream when another user is executing
  const {
    isStreaming: isRemoteStreaming,
    subscribeToStream: subscribeRemoteStream,
    cancelStream: cancelRemoteStream,
  } = useSessionStream({
    onChunk: useCallback((chunkData: any) => {
      updateNodeListRef.current?.(chunkData);
    }, []),
    onStreamEnd: useCallback(() => {
      setIsSessionBusy(false);
      streamCompleteResolverRef.current?.();
      const session = selectedSessionRef.current;
      if (session) {
        loadSessionMessages(session).then((updated) => {
          if (updated) {
            setCurrentSessionMessages(updated.messages);
            setChatSessions(prev =>
              prev.map(s => (s.id === session.id ? { ...s, ...updated } : s)),
            );
          }
        });
      }
    }, [loadSessionMessages]),
    onError: useCallback((error: string) => {
      console.error('Session stream error:', error);
      streamCompleteResolverRef.current?.();
    }, []),
  });

  // ─── Session management ──────────────────────────────────────────────────

  const transformApiDataToSessions = useCallback(
    (apiData: ChatSessionData[]): ChatSession[] =>
      apiData.map((sessionData, index) => {
        const base = transformSessionData(sessionData, index);
        let sharing = false;
        if (base.fromSharedLink && base.blueprintExists && base.blueprintId) {
          sharing = !(sessionData.metadata?.public_usage_scope ?? false);
        }
        return { ...base, isSharingDisabled: sharing };
      }),
    [],
  );

  const handleSessionSelectRef = useRef<(session: ChatSession) => Promise<void>>(null!);

  const fetchChatSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await axios.get(
        `/sessions/session.user.list?userId=${contextUserId}&identityType=${identityType}`,
      );
      const sorted = sortSessionsByTimestamp(
        transformApiDataToSessions(response.data),
      );
      setChatSessions(sorted);

      if (sorted.length > 0 && !selectedSessionRef.current) {
        const target = runId
          ? sorted.find((s) => s.id === runId) ?? sorted[0]
          : sorted[0];
        await handleSessionSelectRef.current(target);
      }
    } catch (err) {
      console.error("Error fetching chat sessions:", err);
      setError("Failed to load chat sessions");
    } finally {
      setIsLoading(false);
    }
  }, [contextUserId, identityType, runId, transformApiDataToSessions]);

  const handleSessionSelect = async (session: ChatSession) => {
    const requestId = ++sessionSelectRequestId.current;
    let current = session;
    setSelectedSession(current);
    setIsSharingDisabled(false);

    if (current.blueprintId) validateSelectedBlueprint(current.blueprintId);

    if (session.blueprintExists && session.blueprintId) {
      try {
        const resolved = await fetchResolvedBlueprint(
          session.blueprintId,
          contextUserId,
          identityType,
          isTeam ? (selectedTeam?.name || teamName) : undefined,
        );
        if (sessionSelectRequestId.current !== requestId) return;
        if (resolved) {
          setBlueprintSpecCache((prev) => {
            const next = new Map(prev);
            next.set(session.blueprintId, resolved.spec_dict);
            return next;
          });
          const blueprintName = resolved.spec_dict?.name || "";
          current = { ...current, blueprintName };

          if (session.fromSharedLink) {
            const disabled = !(resolved.metadata?.usageScope === "public");
            setIsSharingDisabled(disabled);
            current = { ...current, isSharingDisabled: disabled };
          }
          setChatSessions((prev) =>
            prev.map((s) =>
              s.id === current.id ? { ...s, blueprintName: current.blueprintName } : s,
            ),
          );
          setSelectedSession(current);
        }
      } catch {
        // keep defaults
      }
    }

    if (sessionSelectRequestId.current !== requestId) return;

    const updated = await loadSessionMessages(current);
    if (sessionSelectRequestId.current !== requestId) return;

    if (updated) {
      const merged = { ...current, ...updated };
      setSelectedSession(merged);
      setCurrentSessionMessages(merged.messages);
      setChatSessions((prev) =>
        prev.map((s) => (s.id === current.id ? merged : s)),
      );
    } else {
      setCurrentSessionMessages([]);
    }
  };
  handleSessionSelectRef.current = handleSessionSelect;

  // ─── Delete ────────────────────────────────────────────────────────────

  const handleDeleteChat = (session: ChatSession, event: React.MouseEvent) => {
    event.stopPropagation();
    setChatToDelete(session);
    setShowDeleteModal(true);
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete) return;
    setIsDeleting(true);
    try {
      await axios.delete(
        `/sessions/session.delete?sessionId=${chatToDelete.id}`,
      );
      setChatSessions((prev) => prev.filter((s) => s.id !== chatToDelete.id));
      if (selectedSession?.id === chatToDelete.id) {
        setSelectedSession(null);
        setCurrentSessionMessages([]);
      }
      setShowDeleteModal(false);
      setChatToDelete(null);
    } catch (err) {
      console.error("Error deleting chat session:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  // ─── Add flow ──────────────────────────────────────────────────────────

  const handleAddFlow = async () => {
    if (!selectedFlowForModal) return;
    setIsCreatingSession(true);
    try {
      const graphId = selectedFlowForModal.id || `graph-${Date.now()}`;
      await axios.post("/sessions/user.session.create", {
        blueprintId: graphId,
        userId: contextUserId,
        identityType,
      });
      const response = await axios.get(
        `/sessions/session.user.list?userId=${contextUserId}&identityType=${identityType}`,
      );
      const sorted = sortSessionsByTimestamp(
        transformApiDataToSessions(response.data),
      );
      setChatSessions(sorted);
      const newest = sorted.find((s) => s.blueprintId === graphId);
      if (newest) await handleSessionSelect(newest);
      setShowAddFlowModal(false);
      setSelectedFlowForModal(null);
    } catch (err) {
      console.error("Error creating session:", err);
    } finally {
      setIsCreatingSession(false);
    }
  };

  // ─── Streaming / execution ─────────────────────────────────────────────

  const updateNodeList = useCallback(
    (chunkData: any) => {
      const {
        node,
        display_name,
        type,
        chunk,
        state,
        tool,
        output,
        call_id,
        args,
        action,
        plan_id,
        thread_id,
        owner_uid,
        workplan,
      } = chunkData;
      const map = nodeListRef.current;
      let existing = map.get(node);

      if (!existing) {
        existing = {
          node_name: display_name,
          node_uid: node,
          stream: type === "complete" ? "DONE" : "PROGRESS",
          text: "",
          tools: [],
          workplans: [],
        };
        map.set(node, existing);
      }

      switch (type) {
        case "llm_token":
          if (chunk) existing.text += chunk;
          break;
        case "tool_calling":
          if (call_id && tool) {
            if (!existing.tools?.find((t: any) => t.id === call_id)) {
              existing.tools?.push({ id: call_id, name: tool, args });
            }
          }
          break;
        case "tool_result":
          if (call_id && tool && output) {
            const entry = existing.tools?.find((t: any) => t.id === call_id);
            if (entry) entry.output = output;
            else existing.tools?.push({ id: call_id, name: tool, output });
          }
          break;
        case "workplan_snapshot":
          if (plan_id && workplan && action) {
            if (!existing.workplans) existing.workplans = [];
            const snap = {
              type: "workplan_snapshot" as const,
              action: action as "loaded" | "saved" | "deleted",
              plan_id,
              thread_id: thread_id || "",
              owner_uid: owner_uid || node,
              node,
              display_name,
              workplan,
            };
            const idx = existing.workplans.findIndex(
              (wp: any) => wp.plan_id === plan_id,
            );
            if (idx !== -1) existing.workplans[idx] = snap;
            else existing.workplans.push(snap);
          }
          break;
        default:
          break;
      }
    },
    [nodeListRef],
  );
  updateNodeListRef.current = updateNodeList;

  const triggerExecution = useCallback(
    async (sessionPayload: SessionPayload) => {
      try {
        setIsLiveRequest(true);

        await axios.post("/sessions/user.session.submit", {
          sessionId: sessionPayload.sessionId,
          inputs: sessionPayload.inputs,
          scope: globalScope,
          loggedInUser: user?.username || "default",
        });

        subscribeRemoteStream(sessionPayload.sessionId);

        await new Promise<void>((resolve) => {
          let resolved = false;
          const done = () => {
            if (resolved) return;
            resolved = true;
            clearInterval(statusPoll);
            resolve();
          };

          streamCompleteResolverRef.current = done;

          const statusPoll = setInterval(async () => {
            try {
              const statusRes = await axios.get(
                `/sessions/session.status.get?sessionId=${sessionPayload.sessionId}`,
              );
              const status = statusRes.data;
              if (status !== "RUNNING" && status !== "QUEUED") {
                done();
              }
            } catch { /* ignore polling errors */ }
          }, 2000);
        });
      } catch (err) {
        console.error("Error communicating with chat API", err);
      } finally {
        setIsLiveRequest(false);
        streamCompleteResolverRef.current = null;
        try {
          const res = await axios.get(
            `/sessions/session.state.get?sessionId=${sessionPayload.sessionId}`,
          );
          return res.data.output;
        } catch (err) {
          console.error("Error fetching session state:", err);
          throw err;
        }
      }
    },
    [globalScope, user?.username, subscribeRemoteStream],
  );

  // ─── Collaboration: join / leave / heartbeat / poll ──────────────────────

  const joinSession = useCallback(async (sessionId: string) => {
    const username = user?.username || "default";
    try {
      await axios.post("/collaboration/session.join", {
        sessionId,
        userId: username,
        displayName: user?.name || username,
        role: "collaborator",
      });
      joinedSessionRef.current = sessionId;
    } catch {
      // collaboration service may be unavailable — degrade gracefully
    }
  }, [user]);

  const leaveSession = useCallback(async (sessionId: string) => {
    const username = user?.username || "default";
    try {
      await axios.post("/collaboration/session.leave", {
        sessionId,
        userId: username,
      });
    } catch {
      // best-effort
    }
    if (joinedSessionRef.current === sessionId) {
      joinedSessionRef.current = null;
    }
  }, [user]);

  const sendHeartbeat = useCallback(async () => {
    const sid = joinedSessionRef.current;
    if (!sid) return;
    const username = user?.username || "default";
    try {
      await axios.post("/collaboration/session.heartbeat", {
        sessionId: sid,
        userId: username,
      });
    } catch {
      // best-effort
    }
  }, [user]);

  const fetchParticipants = useCallback(async (sessionId: string) => {
    try {
      const res = await axios.get(
        `/collaboration/session.participants?sessionId=${sessionId}`,
      );
      const participants: string[] =
        (res.data?.participants || []).map((p: any) => p.user_id);
      setSessionParticipants(prev => {
        const existing = prev[sessionId];
        if (
          existing &&
          existing.length === participants.length &&
          existing.every((u, i) => u === participants[i])
        ) return prev;
        return { ...prev, [sessionId]: participants };
      });
    } catch {
      // collaboration service unavailable
    }
  }, []);

  const pollSessionUpdates = useCallback(async () => {
    const session = selectedSessionRef.current;
    if (!session) return;

    // Refresh session list every ~15s so new sessions from other users appear
    sessionListPollCounterRef.current += 1;
    if (sessionListPollCounterRef.current % 5 === 0) {
      try {
        const listRes = await axios.get(
          `/sessions/session.user.list?userId=${contextUserIdRef.current}&identityType=${identityTypeRef.current}`,
        );
        const sorted = sortSessionsByTimestamp(
          transformApiDataToSessions(listRes.data),
        );
        setChatSessions(sorted);
      } catch { /* ignore */ }
    }

    // Check session status to detect remote execution
    if (!isLiveRequestRef.current) {
      try {
        const statusRes = await axios.get(
          `/sessions/session.status.get?sessionId=${session.id}`,
        );
        const status = statusRes.data;
        const busy = status === "RUNNING" || status === "QUEUED";
        setIsSessionBusy(busy);
      } catch {
        setIsSessionBusy(false);
      }
    }

    // Always poll messages — stable IDs prevent glitching, and
    // the ChatInterface skips the sync while actively streaming.
    const updated = await loadSessionMessages(session);
    if (updated) {
      setCurrentSessionMessages(updated.messages);
      setChatSessions(prev =>
        prev.map(s => (s.id === session.id ? { ...s, ...updated } : s)),
      );
    }

    // Always poll participants
    await fetchParticipants(session.id);

    // Poll typing indicators
    try {
      const typingRes = await axios.get(
        `/collaboration/session.typing?sessionId=${session.id}`,
      );
      const currentUser = user?.username || "default";
      const others = (typingRes.data?.typingUsers || []).filter(
        (u: string) => u !== currentUser,
      );
      setTypingUsers(others);
    } catch {
      // typing poll failed — ignore
    }
  }, [loadSessionMessages, fetchParticipants, user?.username]);

  const getSessionParticipantMembers = useCallback((sessionId: string): MemberDisplay[] => {
    const participants = sessionParticipants[sessionId];
    if (!participants || participants.length === 0) return [];
    return participants.map((username, idx) => {
      const existing = teamMembers.find(m => m.id === username);
      return existing || buildMemberDisplay(username, teamMembers.length + idx);
    });
  }, [sessionParticipants, teamMembers]);

  // Keep refs in sync for stable interval callbacks
  useEffect(() => { selectedSessionRef.current = selectedSession; }, [selectedSession]);
  useEffect(() => { isLiveRequestRef.current = isLiveRequest; }, [isLiveRequest]);
  useEffect(() => { contextUserIdRef.current = contextUserId; }, [contextUserId]);
  useEffect(() => { identityTypeRef.current = identityType; }, [identityType]);

  // Subscribe to remote stream when session becomes busy from another user
  useEffect(() => {
    const justBecameBusy = isSessionBusy && !wasSessionBusyRef.current;
    wasSessionBusyRef.current = isSessionBusy;

    if (justBecameBusy && !isLiveRequest && selectedSession) {
      clearStream();
      subscribeRemoteStream(selectedSession.id);
    }
    if (!isSessionBusy && !isLiveRequest) {
      cancelRemoteStream();
    }
  }, [isSessionBusy, isLiveRequest, selectedSession?.id]);

  // ─── Effects ───────────────────────────────────────────────────────────

  useEffect(() => {
    setSelectedSession(null);
    setCurrentSessionMessages([]);
    fetchChatSessions();
  }, [contextUserId, identityType]);

  // Join/leave session + polling when selected session changes
  useEffect(() => {
    // Leave previous session
    const previousSession = joinedSessionRef.current;
    if (previousSession && previousSession !== selectedSession?.id) {
      leaveSession(previousSession);
    }

    // Reset transient state for new session
    setIsSessionBusy(false);
    setTypingUsers([]);
    wasSessionBusyRef.current = false;
    cancelRemoteStream();
    clearStream();

    // Clear previous timers
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);

    if (!selectedSession) return;

    // Join new session
    joinSession(selectedSession.id);
    fetchParticipants(selectedSession.id);

    // Immediate poll to detect remote execution + load latest messages
    pollSessionUpdates();

    // Poll for messages + participants
    pollTimerRef.current = setInterval(pollSessionUpdates, COLLAB_POLL_INTERVAL);

    // Heartbeat to keep presence alive
    heartbeatTimerRef.current = setInterval(sendHeartbeat, COLLAB_HEARTBEAT_INTERVAL);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, [selectedSession?.id]);

  // Leave session on unmount
  useEffect(() => {
    return () => {
      cancelRemoteStream();
      if (joinedSessionRef.current) {
        leaveSession(joinedSessionRef.current);
      }
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, []);

  // ─── Loading / Error states ────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading sessions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        {error}
      </div>
    );
  }

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>
        <CollaborationHubSessionSidebar
          chatSessions={chatSessions}
          selectedSession={selectedSession}
          isLiveRequest={isLiveRequest}
          onSelectSession={handleSessionSelect}
          onDeleteChat={handleDeleteChat}
          onOpenAddFlow={() => setShowAddFlowModal(true)}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
        <CollaborationHubMainColumn
          selectedSession={selectedSession}
          isLiveRequest={isLiveRequest}
          isSessionBusy={isSessionBusy}
          currentSessionMessages={currentSessionMessages}
          isSharingDisabled={isSharingDisabled}
          isBlueprintValid={isBlueprintValid}
          isValidatingBlueprint={isValidatingBlueprint}
          typingUsers={typingUsers}
          teamMembers={teamMembers}
          triggerExecution={triggerExecution}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
        <CollaborationHubRightPanel
          selectedSession={selectedSession}
          isLiveRequest={isLiveRequest}
          isSessionBusy={isSessionBusy}
          teamName={teamName}
          chatSessionsLength={chatSessions.length}
          blueprintSpecCache={blueprintSpecCache}
          blueprintValidationResults={blueprintValidationResults}
          isValidatingBlueprint={isValidatingBlueprint}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
      </div>

      <CollaborationHubModals
        showAddFlowModal={showAddFlowModal}
        setShowAddFlowModal={setShowAddFlowModal}
        selectedFlowForModal={selectedFlowForModal}
        setSelectedFlowForModal={setSelectedFlowForModal}
        isCreatingSession={isCreatingSession}
        onAddFlowConfirm={handleAddFlow}
        showDeleteModal={showDeleteModal}
        setShowDeleteModal={setShowDeleteModal}
        chatToDelete={chatToDelete}
        isDeleting={isDeleting}
        onConfirmDelete={confirmDeleteChat}
        onDeleteCancel={() => setChatToDelete(null)}
      />
    </>
  );
}
