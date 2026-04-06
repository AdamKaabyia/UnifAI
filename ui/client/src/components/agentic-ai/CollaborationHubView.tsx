import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  CustomDialogContent,
} from "@/components/ui/dialog";
import { Users, Trash2, Plus, MessageSquare, Network } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import GraphDisplay from "./graphs/GraphDisplay";
import WorkflowsPanel from "./WorkflowsPanel";
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

const COLLAB_POLL_INTERVAL = 3000;
const COLLAB_HEARTBEAT_INTERVAL = 30000;

// ─── Types ───────────────────────────────────────────────────────────────────

const MEMBER_COLORS = [
  "from-blue-500 to-blue-600",
  "from-emerald-500 to-emerald-600",
  "from-pink-500 to-pink-600",
  "from-orange-500 to-orange-600",
  "from-violet-500 to-violet-600",
  "from-cyan-500 to-cyan-600",
  "from-amber-500 to-amber-600",
  "from-rose-500 to-rose-600",
];

export interface MemberDisplay {
  id: string;
  name: string;
  initials: string;
  color: string;
}

export function buildMemberDisplay(username: string, index: number): MemberDisplay {
  const parts = username.split(/[._\-\s@]+/).filter(Boolean);
  const initials =
    parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : username.slice(0, 2).toUpperCase();
  return {
    id: username,
    name: username,
    initials,
    color: MEMBER_COLORS[index % MEMBER_COLORS.length],
  };
}

export function CollabAvatar({ member, size = "sm" }: { member: MemberDisplay; size?: "xs" | "sm" }) {
  const sizeClasses = { xs: "w-5 h-5 text-[9px]", sm: "w-7 h-7 text-[10px]" };
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-gradient-to-br ${member.color} flex items-center justify-center font-bold text-white flex-shrink-0`}>
      {member.initials}
    </div>
  );
}

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
  const contextUserId = isTeam ? selectedTeam!.name : (user?.username || "default");
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

      if (sorted.length > 0 && !selectedSession) {
        const target = runId
          ? sorted.find((s) => s.id === runId) ?? sorted[0]
          : sorted[0];
        await handleSessionSelect(target);
      }
    } catch (err) {
      console.error("Error fetching chat sessions:", err);
      setError("Failed to load chat sessions");
    } finally {
      setIsLoading(false);
    }
  }, [contextUserId, identityType, runId]);

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
        {/* ── Sessions Sidebar ── */}
        <div className="w-[280px] border-r border-gray-800 bg-background-card flex flex-col flex-shrink-0">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <span className="font-semibold text-sm text-white">
              Sessions ({chatSessions.length})
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-primary hover:bg-primary/20"
              onClick={() => setShowAddFlowModal(true)}
              title="New session from workflow"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {chatSessions.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-xs">
                No sessions yet. Load a workflow to get started.
              </div>
            ) : (
              chatSessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => handleSessionSelect(session)}
                  className={`group px-4 py-3 border-b border-gray-800/50 cursor-pointer transition-colors ${
                    selectedSession?.id === session.id
                      ? "bg-primary/10 border-l-2 border-l-primary"
                      : "hover:bg-white/[.02]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-xs text-white truncate flex-1">
                      {session.blueprintName || session.title}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-5 w-5 p-0 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                      onClick={(e) => handleDeleteChat(session, e)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <motion.div
                      className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-emerald-400"
                      animate={
                        selectedSession?.id === session.id && isLiveRequest
                          ? { opacity: [1, 0.4, 1] }
                          : {}
                      }
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    <span className="text-[11px] text-gray-500">
                      {session.lastActive}
                    </span>
                  </div>
                  {session.blueprintName && session.blueprintName !== session.title && (
                    <div className="flex items-center gap-1 mt-1.5">
                      <MessageSquare className="h-2.5 w-2.5 text-gray-600" />
                      <span className="text-[10px] text-gray-600 truncate">
                        {session.title}
                      </span>
                    </div>
                  )}
                  {(() => {
                    const participants = getSessionParticipantMembers(session.id);
                    if (participants.length === 0) return null;
                    return (
                      <div className="flex items-center mt-2 -space-x-1">
                        {participants.slice(0, 3).map((m) => (
                          <div
                            key={m.id}
                            className="ring-2 ring-background-card rounded-full"
                          >
                            <CollabAvatar member={m} size="xs" />
                          </div>
                        ))}
                        {participants.length > 3 && (
                          <span className="text-[10px] text-gray-600 ml-2">
                            +{participants.length - 3}
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Main Chat Area ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chat header */}
          <div className="px-5 py-3 border-b border-gray-800 bg-background-surface flex items-center gap-3 flex-shrink-0">
            {selectedSession ? (
              <>
                <motion.div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${(isLiveRequest || isSessionBusy) ? "bg-emerald-400" : "bg-gray-500"}`}
                  animate={(isLiveRequest || isSessionBusy) ? { opacity: [1, 0.4, 1] } : {}}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="font-bold text-sm text-white flex-1 truncate">
                  {selectedSession.blueprintName || selectedSession.title}
                </span>
                {(() => {
                  const participants = selectedSession ? getSessionParticipantMembers(selectedSession.id) : [];
                  return (
                    <div className="flex items-center -space-x-1.5">
                      {participants.slice(0, 4).map((m) => (
                        <div
                          key={m.id}
                          className="ring-2 ring-background-surface rounded-full"
                        >
                          <CollabAvatar member={m} size="xs" />
                        </div>
                      ))}
                      {participants.length > 0 && (
                        <span className="text-xs text-gray-500 ml-2">
                          {participants.length} active
                        </span>
                      )}
                    </div>
                  );
                })()}
              </>
            ) : (
              <span className="text-sm text-gray-500">
                Select a session to start
              </span>
            )}
          </div>

          {/* Chat content */}
          <div className="flex-1 min-h-0">
            {selectedSession ? (
              <ChatInterface
                key={selectedSession.id}
                runId={selectedSession.id}
                triggerExecution={triggerExecution}
                initialMessages={currentSessionMessages}
                blueprintExists={selectedSession.blueprintExists}
                isSharingDisabled={isSharingDisabled}
                blueprintValid={isBlueprintValid}
                isValidatingBlueprint={isValidatingBlueprint}
                isLiveRequest={isLiveRequest || isSessionBusy}
                collaborationMode={true}
                teamMembers={teamMembers}
                typingUsers={typingUsers}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                <div className="text-center">
                  <Users className="h-10 w-10 mx-auto mb-3 text-gray-600" />
                  <p className="font-medium text-gray-400">No session selected</p>
                  <p className="text-xs mt-1">
                    Choose a session from the sidebar or load a workflow
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Right Panel — Live Workflow + Participants + Info ── */}
        <div className="w-[340px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex">
          {/* Live Workflow Graph */}
          <div className="flex-1 min-h-0 flex flex-col border-b border-gray-800">
            <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <Network className="w-3.5 h-3.5 text-primary" />
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  Live Workflow
                </span>
              </div>
              {(isLiveRequest || isSessionBusy) && (
                <div className="flex items-center gap-1.5">
                  <motion.div
                    className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                  <span className="text-[10px] text-emerald-400 font-medium">Running</span>
                </div>
              )}
            </div>
            <div className="flex-1 min-h-0 bg-background-dark">
              {selectedSession?.blueprintId ? (
                <GraphDisplay
                  key={`collab-live-${selectedSession.id}`}
                  blueprintId={selectedSession.blueprintId}
                  specDict={blueprintSpecCache.get(selectedSession.blueprintId)}
                  height="100%"
                  showBackground={true}
                  interactive={false}
                  centerInView={true}
                  animated={true}
                  validationResults={blueprintValidationResults}
                  isValidating={isValidatingBlueprint}
                  isLiveRequest={isLiveRequest}
                  isGraphVisible={true}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-600 text-xs">
                  Select a session to view workflow
                </div>
              )}
            </div>
          </div>

          {/* Participants */}
          <div className="px-4 py-3 border-b border-gray-800 flex-shrink-0">
            {(() => {
              const participants = selectedSession ? getSessionParticipantMembers(selectedSession.id) : [];
              return (
                <>
                  <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Active Participants ({participants.length})
                  </div>
                  {participants.length === 0 ? (
                    <div className="text-xs text-gray-600 text-center py-2">
                      No messages sent yet
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {participants.map((m) => (
                        <div key={m.id} className="flex items-center gap-2 py-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                          <CollabAvatar member={m} size="xs" />
                          <span className="text-xs text-gray-300 flex-1 truncate">
                            {m.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              );
            })()}
          </div>

          {/* Session Info */}
          <div className="px-4 py-3 flex-shrink-0">
            <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Session Info
            </div>
            <dl className="text-xs text-gray-500 space-y-1.5">
              <div className="flex justify-between">
                <dt className="font-medium text-gray-400">Team</dt>
                <dd>{teamName}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-gray-400">Blueprint</dt>
                <dd className="truncate ml-2 max-w-[140px]">
                  {selectedSession?.blueprintName || selectedSession?.blueprintId || "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-gray-400">Started</dt>
                <dd>{selectedSession?.lastActive || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-gray-400">Status</dt>
                <dd className={(isLiveRequest || isSessionBusy) ? "text-emerald-400 font-semibold" : "text-gray-500"}>
                  {(isLiveRequest || isSessionBusy) ? "Running" : selectedSession ? "Idle" : "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-gray-400">Sessions</dt>
                <dd>{chatSessions.length}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      {/* ── Add Flow Modal ── */}
      <Dialog open={showAddFlowModal} onOpenChange={setShowAddFlowModal}>
        <CustomDialogContent className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="flex-shrink-0 pb-4">
            <DialogTitle className="text-lg">Start New Session</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-hidden">
            <div key={`collab-hub-add-${showAddFlowModal}`} className="h-full">
              <WorkflowsPanel
                selectedFlow={selectedFlowForModal}
                onFlowSelect={(flow: FlowObject | null) => setSelectedFlowForModal(flow)}
                showActiveStatus={false}
                showDeleteButton={false}
                height="100%"
                graphProps={{ showBackground: true, interactive: true }}
              />
            </div>
          </div>
          <DialogFooter className="flex-shrink-0 pt-4 border-t border-gray-800">
            <Button
              variant="outline"
              onClick={() => {
                setShowAddFlowModal(false);
                setSelectedFlowForModal(null);
              }}
              disabled={isCreatingSession}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddFlow}
              disabled={!selectedFlowForModal || isCreatingSession}
              className="bg-[#03DAC6] hover:bg-opacity-80 text-black"
            >
              {isCreatingSession ? "Creating..." : "Start Session"}
            </Button>
          </DialogFooter>
        </CustomDialogContent>
      </Dialog>

      {/* ── Delete Confirmation ── */}
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Session</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{chatToDelete?.title}&quot;?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setShowDeleteModal(false);
                setChatToDelete(null);
              }}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteChat}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
