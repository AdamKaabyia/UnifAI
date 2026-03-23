import React, { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Users, Clock, Trash2, Plus, Columns3, Network } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import ExecutionStream from "./ExecutionStream";
import GraphDisplay from "./graphs/GraphDisplay";
import axios from '../../http/axiosAgentConfig'
import { fetchResolvedBlueprint } from '@/api/blueprints'
import { useStreamingData } from './StreamingDataContext'
import { useAuth } from "@/contexts/AuthContext";
import WorkflowsPanel from "./WorkflowsPanel";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  CustomDialogContent,
} from "@/components/ui/dialog";
import { GraphFlow, FlowObject } from "./graphs/interfaces";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useBlueprintValidation } from "@/hooks/use-blueprint-validation";

import { ChatSession, ChatMessage, ChatSessionData, SessionStateData } from "@/types/session";
import {transformSessionData, sortSessionsByTimestamp} from "@/utils/sessionHelpers";
import { useSessionManagement } from "@/hooks/use-session-management";
import { useSessionStream } from "@/hooks/use-session-stream";


/**
 * Session execution payload (fire-and-forget submit + stream subscribe pattern)
 */
export type SessionPayload = {
  sessionId: string;
  inputs: { user_prompt: string };
  scope?: 'public' | 'private';
  loggedInUser?: string;
};

type ExecutionTabProps = {
  runId: string | null;
};


type ChunkData = {
  node: string;
  display_name: string;
  type: 'llm_token' | 'complete' | 'tool_calling' | 'tool_result' | 'workplan_snapshot';
  chunk?: string;
  tool?: string;
  output?: string;
  call_id?: string;
  args?: Record<string, any>;
  state?: {
    user_prompt?: string;
  };
  // WorkPlan specific fields
  action?: 'loaded' | 'saved' | 'deleted';
  plan_id?: string;
  thread_id?: string;
  owner_uid?: string;
  workplan?: any; // Will contain the full workplan data
};

/**
 * Loader component displayed while session messages are being fetched.
 * Prevents showing stale messages from the previous session.
 */
const SessionMessagesLoader: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
    <div className="flex flex-col items-center gap-4">
      <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
      <p className="text-gray-400 text-sm">Loading session messages...</p>
    </div>
  </div>
);

export default function ExecutionTab({
  runId
}: ExecutionTabProps): React.ReactElement {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [currentSessionMessages, setCurrentSessionMessages] = useState<ChatMessage[]>([]);
  const [showExecutionStream, setShowExecutionStream] = useState(false);
  const [isActiveChatSession, setIsActiveChatSession] = useState(true);
  const [isLiveRequest, setIsLiveRequest] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [globalScope, setGlobalScope] = useState<'public' | 'private'>('public');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showAddFlowModal, setShowAddFlowModal] = useState(false);
  const [selectedFlowForModal, setSelectedFlowForModal] = useState<FlowObject | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isLoadingSessionMessages, setIsLoadingSessionMessages] = useState(false);
  // Three panel widths: Available Chats, ChatInterface, Blueprint Graph
  const [chatSidebarWidth, setChatSidebarWidth] = useState(15);
  const [chatInterfaceWidth, setChatInterfaceWidth] = useState(55);
  const [blueprintGraphWidth, setBlueprintGraphWidth] = useState(30);
  const [isResizing, setIsResizing] = useState(false);
  const [activeResizer, setActiveResizer] = useState<'left' | 'right' | null>(null);
  const [isSharingDisabled, setIsSharingDisabled] = useState<boolean>(false);
  const [sharedLinkBlueprintName, setSharedLinkBlueprintName] = useState<string>("");
  const [isLoadingBlueprintName, setIsLoadingBlueprintName] = useState<boolean>(false);
  const [isBlueprintGraphHidden, setIsBlueprintGraphHidden] = useState(false);
  const [savedBlueprintGraphWidth, setSavedBlueprintGraphWidth] = useState(30);
  // Cache: resolved spec_dict per blueprintId for the side GraphDisplay (contains resource names)
  const [blueprintSpecCache, setBlueprintSpecCache] = useState<Map<string, any>>(new Map());
  const [carouselMode, setCarouselMode] = useState<'normal' | 'chat' | 'graph'>('normal');

  const { nodeListRef, forceUpdate, clearStream } = useStreamingData();
  const { user } = useAuth();
  
  // Ref to hold the updateNodeList callback for use in stream subscription
  const updateNodeListRef = useRef<((chunkData: any) => void) | null>(null);

  // Race-condition guard for session switching.
  //
  // handleSessionSelect performs multiple async calls (fetchResolvedBlueprint,
  // loadSessionMessages).  If the user clicks Session A and then quickly clicks
  // Session B before A's fetches resolve, A's responses would arrive *after*
  // we've already moved to B – overwriting B's state with A's data (wrong graph,
  // wrong messages, wrong sharing status).
  //
  // We increment this counter at the start of every selection.  Each async step
  // checks "is this still the active request?" before writing state.  If the user
  // switched away in the meantime, the stale response is silently discarded.
  const sessionSelectRequestId = useRef(0);
  
  // Derived state: Chat-only mode is active for shared link sessions
  // This single flag drives all chat-only experience behaviors (no graph, no resize, etc.)
  const isChatOnlyMode = selectedSession?.fromSharedLink ?? false;
  
  // Blueprint validation hook
  const {
    isValidating: isValidatingBlueprint,
    validationResults: blueprintValidationResults,
    isValid: isBlueprintValid,
    validateBlueprint: validateSelectedBlueprint,
  } = useBlueprintValidation({
    showToastOnFailure: true,
  });

  // Set carousel mode directly: allows switching between normal/chat/graph views
  const handleSetCarouselMode = useCallback((mode: 'normal' | 'chat' | 'graph') => {
    // Don't allow carousel changes for chat-only sessions
    if (isChatOnlyMode) {
      return;
    }
    
    const availableWidth = 100 - chatSidebarWidth;
    
    switch (mode) {
      case 'normal':
        // Split view: Both visible with default widths
        setCarouselMode('normal');
        setChatInterfaceWidth(55);
        setBlueprintGraphWidth(availableWidth - 55);
        break;
      case 'chat':
        // Full chat: ChatInterface takes full width
        setCarouselMode('chat');
        setChatInterfaceWidth(availableWidth);
        setBlueprintGraphWidth(0);
        break;
      case 'graph':
        // Full graph: Blueprint Graph takes full width
        setCarouselMode('graph');
        setChatInterfaceWidth(0);
        setBlueprintGraphWidth(availableWidth);
        break;
    }
  }, [isChatOnlyMode, chatSidebarWidth]);

  // Resizable panel handlers
  const handleMouseDown = (resizer: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    setActiveResizer(resizer);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !activeResizer) return;
    
    const containerRect = document.querySelector('.resizable-container')?.getBoundingClientRect();
    if (!containerRect) return;

    const mousePosition = ((e.clientX - containerRect.left) / containerRect.width) * 100;
    
    if (activeResizer === 'left') {
      // Resizing between Available Chats and ChatInterface
      const minChatSidebar = 15;
      const maxChatSidebar = 35;
      const newChatSidebarWidth = Math.min(Math.max(mousePosition, minChatSidebar), maxChatSidebar);
      const remainingWidth = 100 - newChatSidebarWidth;
      const newChatInterfaceWidth = (chatInterfaceWidth / (chatInterfaceWidth + blueprintGraphWidth)) * remainingWidth;
      const newBlueprintGraphWidth = remainingWidth - newChatInterfaceWidth;
      
      setChatSidebarWidth(newChatSidebarWidth);
      setChatInterfaceWidth(newChatInterfaceWidth);
      setBlueprintGraphWidth(newBlueprintGraphWidth);
    } else if (activeResizer === 'right') {
      // Resizing between ChatInterface and Blueprint Graph
      const availableWidth = 100 - chatSidebarWidth;
      const relativePosition = ((mousePosition - chatSidebarWidth) / availableWidth) * 100;
      const minChatInterface = 25;
      const maxChatInterface = 100; // Allow Blueprint Graph to collapse to 0%
      const newChatInterfaceRatio = Math.min(Math.max(relativePosition, minChatInterface), maxChatInterface);
      
      const newChatInterfaceWidth = (availableWidth * newChatInterfaceRatio) / 100;
      const newBlueprintGraphWidth = availableWidth - newChatInterfaceWidth;
      
      setChatInterfaceWidth(newChatInterfaceWidth);
      setBlueprintGraphWidth(newBlueprintGraphWidth);
    }
  }, [isResizing, activeResizer, chatSidebarWidth, chatInterfaceWidth, blueprintGraphWidth]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    setActiveResizer(null);
  }, []);

  // Add event listeners for mouse move and up
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
    } else {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  const { currentMessages, loadSessionMessages, clearMessages, setCurrentMessages } =
    useSessionManagement();

  const handleGlobalScopeToggle = () => {
    setGlobalScope(prevScope => prevScope === 'public' ? 'private' : 'public');
  };

  // Derives sessions from the sessions API data only – no extra API calls.
  // Blueprint names and fresh sharing status are loaded on-demand
  // in handleSessionSelect via fetchResolvedBlueprint.
  // (Will simplify further once Odai's lightweight resolved API lands.)
  const transformApiDataToSessions = (apiData: ChatSessionData[]): ChatSession[] => {
    return apiData.map((sessionData, index) => {
      const base = transformSessionData(sessionData, index);

      // Derive initial sharing status from session metadata.
      // Re-verified against the blueprint in handleSessionSelect.
      let isSharingDisabled = false;
      if (base.fromSharedLink && base.blueprintExists && base.blueprintId) {
        isSharingDisabled = !(sessionData.metadata?.public_usage_scope ?? false);
      }

      return { ...base, isSharingDisabled };
    });
  };

  // Fetch chat sessions from API
  const fetchChatSessions = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const userId = user?.username || "default";
      const response = await axios.get(`/sessions/session.user.list?userId=${userId}`);
      const transformedSessions = transformApiDataToSessions(response.data);

      // Sort chat sessions based on the latest date
      const sortedSessions = sortSessionsByTimestamp(transformedSessions);
      setChatSessions(sortedSessions);

      // Auto-select the first session if available - use handleSessionSelect to trigger status checks
      if (sortedSessions.length > 0 && !selectedSession) {
        const firstSession = sortedSessions[0];
        // Use handleSessionSelect to ensure status checks and other logic run
        await handleSessionSelect(firstSession);
      }
    } catch (err) {
      console.error('Error fetching chat sessions:', err);
      setError('Failed to load chat sessions');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle session selection
  const handleSessionSelect = async (session: ChatSession) => {
    // Increment request id so that any in-flight async work from a previous
    // selection is silently discarded when it resolves.
    const requestId = ++sessionSelectRequestId.current;

    let currentSession = session;
    setSelectedSession(currentSession);

    // Show loader immediately and clear old messages to prevent showing stale data
    setIsLoadingSessionMessages(true);
    setCurrentSessionMessages([]);

    // Cancel any existing stream subscription before switching sessions
    // This ensures the UI stops receiving events from the previous session
    sessionStream.cancelStream();

    // Reset streaming state when switching sessions
    // This clears any existing node data from the previous session
    clearStream();
    setIsLiveRequest(false);

    // Reset sharing-disabled state immediately so a previously disabled session
    // doesn't bleed into the newly selected (possibly valid) session.
    setIsSharingDisabled(false);
    
    if (currentSession.blueprintId) {
      validateSelectedBlueprint(currentSession.blueprintId);
    }
    
    // Reset blueprint name and loading state when switching sessions
    setSharedLinkBlueprintName("");
    setIsLoadingBlueprintName(false);
    
    // For chat-only sessions (shared links), configure panel layout for message area
    // Note: Using session.fromSharedLink here (not isChatOnlyMode) because state hasn't updated yet
    if (session.fromSharedLink) {
      setCarouselMode('normal'); // Ensure normal mode for chat-only sessions
      setBlueprintGraphWidth(30); // Set width for the chat-only message area
      const remainingWidth = 100 - chatSidebarWidth - 30;
      setChatInterfaceWidth(remainingWidth);
    }
    // For regular sessions, keep current carousel mode
    
    // Fetch resolved blueprint by ID – serves two purposes:
    // 1. Extract sharing status from metadata.usageScope
    // 2. Cache resolved spec_dict for the side GraphDisplay (resource names preserved)
    if (!session.blueprintExists) {
      // Workflow deleted – sharing state already reset above; deleted message will show instead.
    } else if (session.blueprintId) {
      setIsLoadingBlueprintName(true);
      try {
        const userId = user?.username || "default";
        const resolvedBlueprint = await fetchResolvedBlueprint(session.blueprintId, userId);

        // Bail out if the user switched to a different session while we were fetching
        if (sessionSelectRequestId.current !== requestId) return;

        if (resolvedBlueprint) {
          // Cache the resolved spec_dict for the GraphDisplay
          setBlueprintSpecCache(prev => {
            const next = new Map(prev);
            next.set(session.blueprintId, resolvedBlueprint.spec_dict);
            return next;
          });

          // Extract blueprint name (only available from the resolved response)
          const blueprintName = resolvedBlueprint.spec_dict?.name || "";
          currentSession = { ...currentSession, blueprintName };

          // Extract sharing status from metadata.usageScope
          if (session.fromSharedLink) {
            const isPublic = resolvedBlueprint.metadata?.usageScope === "public";
            const disabled = !isPublic;
            setIsSharingDisabled(disabled);
            currentSession = { ...currentSession, isSharingDisabled: disabled };
            setChatSessions(prev => prev.map(s => 
              s.id === currentSession.id ? { ...s, blueprintName, isSharingDisabled: disabled } : s
            ));
          } else if (blueprintName) {
            setChatSessions(prev => prev.map(s => 
              s.id === currentSession.id ? { ...s, blueprintName } : s
            ));
          }
          setSelectedSession(currentSession);
        }
      } catch (error) {
        // Keep defaults from initial load
        console.error("Error fetching resolved blueprint:", error);
      }
      finally {
        if (sessionSelectRequestId.current === requestId) {
          setIsLoadingBlueprintName(false);
        }
      }
    }

    // Bail out if the user switched to a different session while we were fetching
    if (sessionSelectRequestId.current !== requestId) return;
    
    // Load session messages, merging with currentSession to preserve derived
    // fields (blueprintName, isSharingDisabled) that loadSessionMessages may not return.
    const updatedSession = await loadSessionMessages(currentSession);

    // Final stale check before applying message state
    if (sessionSelectRequestId.current !== requestId) return;

    if (updatedSession) {
      const merged = { ...currentSession, ...updatedSession };
      setSelectedSession(merged);
      setCurrentSessionMessages(merged.messages);
      setChatSessions(prevSessions =>
        prevSessions.map(s => (s.id === currentSession.id ? merged : s))
      );
    } else {
      setCurrentSessionMessages([]);
    }
    setIsLoadingSessionMessages(false);

    // Check if this session has an active Redis stream and reconnect if so
    // This enables persistent streaming - when user navigates away and returns,
    // they can reconnect to the live stream and continue seeing updates
    // Note: This runs in the background - we don't block session selection on it
    sessionStream.checkAndReconnect(session.id).then(hasActiveStream => {
      if (hasActiveStream) {
        setIsLiveRequest(true);
      }
    });
  };

  // Handle delete chat
  const handleDeleteChat = (session: ChatSession, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent session selection when clicking delete
    setChatToDelete(session);
    setShowDeleteModal(true);
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete) return;

    setIsDeleting(true);
    try {
      const userId = user?.username || "default";
      await axios.delete(`/sessions/session.delete?sessionId=${chatToDelete.id}`);

      // Remove the deleted session from the list
      setChatSessions(prevSessions => prevSessions.filter(session => session.id !== chatToDelete.id));

      // If the deleted session was selected, clear the selection
      if (selectedSession?.id === chatToDelete.id) {
        setSelectedSession(null);
        setCurrentSessionMessages([]);
      }

      setShowDeleteModal(false);
      setChatToDelete(null);
    } catch (error) {
      console.error('Error deleting chat session:', error);
      // Handle error (you might want to show a toast notification here)
    } finally {
      setIsDeleting(false);
    }
  };

  const cancelDeleteChat = () => {
    setShowDeleteModal(false);
    setChatToDelete(null);
  };

  // Handle add flow modal
  const handleAddFlowClick = () => {
    setShowAddFlowModal(true);
  };

  const handleFlowSelect = (flow: FlowObject | null): void => {
    setSelectedFlowForModal(flow);
  };

  const handleAddFlow = async () => {
    if (!selectedFlowForModal) return;

    setIsCreatingSession(true);
    try {
      const graphId = selectedFlowForModal.id || `graph-${Date.now()}`;

      const selectedBlueprint = {
        blueprintId: graphId,
        userId: user?.username || "default",
      };

      await axios.post(
        "/sessions/user.session.create",
        selectedBlueprint,
      );

      // Fetch updated sessions
      const userId = user?.username || "default";
      const response = await axios.get(`/sessions/session.user.list?userId=${userId}`);
      const transformedSessions = transformApiDataToSessions(response.data);
      const sortedSessions = sortSessionsByTimestamp(transformedSessions);
      setChatSessions(sortedSessions);

      // Auto-select the newly created session
      const newestSession = sortedSessions.find(session => session.blueprintId === graphId);
      if (newestSession) {
        await handleSessionSelect(newestSession);
      }

      setShowAddFlowModal(false);
      setSelectedFlowForModal(null);
    } catch (error) {
      console.error("Error creating new graph session:", error);
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleCancelAddFlow = () => {
    setShowAddFlowModal(false);
    setSelectedFlowForModal(null);
  };

  // Initialize component with API call
  useEffect(() => {
    fetchChatSessions();
  }, []);

  // Cleanup effect when modal closes to prevent ReactFlow state interference
  useEffect(() => {
    if (!showAddFlowModal && selectedFlowForModal) {
      // Reset selected flow when modal closes to ensure clean state
      setSelectedFlowForModal(null);
    }
  }, [showAddFlowModal]);

  // Tracks each node's streaming state.
  // Aggregates chunks per node.
  // Marks a node as DONE when a type: "complete" event is received for it.
  // Cleanly handles streaming via ReadableStream.
  // This follows clean architecture, maintains readability, and ensures correctness even in noisy or unpredictable stream outputs.
  // Extracts multiple well-formed ["custom", {...}] chunks from the stream text.
  const parseStreamChunk = (chunk: string): any[] => {
    const parsedChunks: any[] = [];
    const pattern = /\["custom",\s*(\{.*?\})\]/g;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(chunk)) !== null) {
      try {
        const json = JSON.parse(match[1]);
        parsedChunks.push(json);
      } catch (e) {
        console.warn("Failed to parse stream JSON chunk:", match[1]);
      }
    }

    return parsedChunks;
  };

  // Maintains and updates a list of nodes and their stream state (PROGRESS or DONE) while aggregating text.
  const updateNodeList = (chunkData: ChunkData) => {
    const { node, display_name, type, chunk, state, tool, output, call_id, args, action, plan_id, thread_id, owner_uid, workplan } = chunkData;
    const currentText = chunk ?? state?.user_prompt ?? '';
    const map = nodeListRef.current;

    let existing = map.get(node);

    // Initialize the node entry if it doesn't exist
    if (!existing) {
      existing = {
        node_name: display_name,
        node_uid: node,
        stream: type === 'complete' ? 'DONE' : 'PROGRESS',
        text: '',
        tools: [],
        workplans: [],
      };
      map.set(node, existing);
    }

    switch (type) {
      case 'llm_token':
        if (chunk) {
          existing.text += chunk;
        }
        break;

      // case 'complete':
      //   existing.stream = 'DONE';
      //   if (state?.user_prompt && existing.text.trim() === '') {
      //     existing.text = state.user_prompt;
      //   }
      //   break;

      case 'tool_calling':
        if (call_id && tool) {
          const existingTool = existing.tools?.find((t: any) => t.id === call_id);
          if (!existingTool) {
            existing.tools?.push({ id: call_id, name: tool, args });
          }
        }
        break;

      case 'tool_result':
        if (call_id && tool && output) {
          const toolEntry = existing.tools?.find((t: any) => t.id === call_id);
          if (toolEntry) {
            toolEntry.output = output;
          } else {
            existing.tools?.push({ id: call_id, name: tool, output });
          }
        }
        break;

      case 'workplan_snapshot':
        if (plan_id && workplan && action) {
          // Initialize workplans array if it doesn't exist
          if (!existing.workplans) {
            existing.workplans = [];
          }

          // Create the workplan snapshot
          const workplanSnapshot = {
            type: 'workplan_snapshot' as const,
            action: action as 'loaded' | 'saved' | 'deleted',
            plan_id: plan_id,
            thread_id: thread_id || '',
            owner_uid: owner_uid || node,
            node: node,
            display_name: display_name,
            workplan: workplan
          };

          // Find existing workplan or add new one
          const existingPlanIndex = existing.workplans.findIndex(
            (wp: any) => wp.plan_id === plan_id
          );

          if (existingPlanIndex !== -1) {
            // Update existing workplan
            existing.workplans[existingPlanIndex] = workplanSnapshot;
          } else {
            // Add new workplan
            existing.workplans.push(workplanSnapshot);
          }
        }
        break;

      default:
        break;
    }

    // forceUpdate(); // Uncomment if needed to trigger a re-render
  };

  // Keep ref updated with latest updateNodeList function
  updateNodeListRef.current = updateNodeList;

  // Ref to track stream completion promise resolver
  const streamCompleteResolverRef = useRef<(() => void) | null>(null);

  // Redis stream subscription for persistent streaming across page navigation
  // Uses fire-and-forget submit + subscribe pattern
  const sessionStream = useSessionStream({
    onChunk: useCallback((chunkData: any) => {
      updateNodeListRef.current?.(chunkData);
    }, []),
    onStreamEnd: useCallback(() => {
      setIsLiveRequest(false);
      // Resolve any pending completion promise
      if (streamCompleteResolverRef.current) {
        streamCompleteResolverRef.current();
        streamCompleteResolverRef.current = null;
      }
    }, []),
    onError: useCallback((error: string) => {
      console.error('Stream error:', error);
      setIsLiveRequest(false);
      // Resolve any pending completion promise (with error state)
      if (streamCompleteResolverRef.current) {
        streamCompleteResolverRef.current();
        streamCompleteResolverRef.current = null;
      }
    }, []),
  });

  /**
   * Submit a session for execution and stream results.
   * 
   * Uses fire-and-forget pattern:
   * 1. POST /user.session.submit  ← fire & forget (returns 202 immediately)
   * 2. GET /session.stream.subscribe ← real-time events (NDJSON stream)
   * 
   * The streaming is handled by useSessionStream hook, which:
   * - Processes events via onChunk → updateNodeList → nodeListRef
   * - Signals completion via onStreamEnd → setIsLiveRequest(false)
   * 
   * Multiple sessions can run in parallel - we only switch which stream we're listening to.
   */
  const triggerExecution = async (sessionPayload: SessionPayload): Promise<string> => {
    try {
      setIsLiveRequest(true);
      
      // Create a promise that resolves when streaming completes
      const streamCompletePromise = new Promise<void>((resolve) => {
        streamCompleteResolverRef.current = resolve;
      });

      // Submit session and subscribe to stream (fire & forget + immediate subscription)
      await sessionStream.submitAndSubscribe({
        sessionId: sessionPayload.sessionId,
        inputs: sessionPayload.inputs,
        scope: sessionPayload.scope || globalScope,
        loggedInUser: sessionPayload.loggedInUser || user?.username || "default",
      });

      // Wait for streaming to complete (resolved by onStreamEnd callback)
      await streamCompletePromise;

      console.log('Streaming completed.');
      console.log('Final Node List:', nodeListRef.current);

      // Fetch the final session output
      const session_response = await axios.get(
        `/sessions/session.chat.get?sessionId=${sessionPayload.sessionId}`
      );
      return session_response.data.output;
    } catch (error) {
      console.error('Error in session execution:', error);
      setIsLiveRequest(false);
      throw error;
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-400">Loading chat sessions...</div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-red-400">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-heading font-semibold">AI Assistant</h2>
          <p className="text-sm text-gray-400 mt-1">
            Interact with your AI assistant and monitor execution details
          </p>
        </div>

          {/* <UmamiTrack event={UmamiEvents.AGENT_CHAT_TOGGLE_EXECUTION_STREAM_BUTTON}> */}
            {/* Commenting the next part out due to Nir's request. If and when commenting back in need to take care of coloring. */}
        {/* <Button
            className={`flex items-center gap-2 ${isActiveChatSession ? "bg-[#03DAC6] hover:bg-opacity-80" : "bg-gray-700 text-gray-300 cursor-not-allowed"}`}
            onClick={() => setShowExecutionStream(!showExecutionStream)}
            disabled={!isActiveChatSession}
            >
            <SplitSquareVertical className="h-4 w-4" />
            {showExecutionStream ? "Hide" : "Open"} Execution Stream
            </Button> */}
          {/* </UmamiTrack> */}
      </div>

      <div className="flex resizable-container gap-0" style={{ height: "calc(100vh - 230px)" }}>
        {/* Available Chats Sidebar - Dynamic width */}
        <div className="flex-shrink-0" style={{ width: `${chatSidebarWidth}%` }}>
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col mr-0">
            <CardHeader className="py-3 px-4 border-b border-gray-800 overflow-hidden">
              <div className="flex justify-between items-center min-w-0 w-full max-w-full">
                <CardTitle className="text-sm font-medium truncate flex-1 min-w-0 mr-2">
                  Available Chats ({chatSessions.length})
                </CardTitle>
                <div className="flex items-center gap-1 flex-shrink-0 max-w-fit">
                  {/* Commenting the next part out since it's related to our RAG system. If and when commenting back in need to take care of coloring. */}
                  {/* Global Scope Toggle */}
                  {/* <UmamiTrack event={UmamiEvents.AGENT_CHAT_TOGGLE_GLOBAL_SCOPE_BUTTON}> */}
                  {/* <Switch.Root
                    className="relative w-20 h-5 rounded-full bg-gray-600 data-[state=checked]:bg-[#03DAC6] transition-colors cursor-pointer flex-shrink-0"
                    checked={globalScope === 'public'}
                    onCheckedChange={handleGlobalScopeToggle}
                    id="scope-switch"
                    title={`Current scope: ${globalScope}`}
                  > */}
                    {/* Background label
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white pointer-events-none select-none">
                      {globalScope === 'public' ? 'Public' : 'Private'}
                    </span> */}

                    {/* Switch thumb */}
                    {/* <Switch.Thumb
                      className="absolute top-[1px] left-[1px] h-4 w-4 rounded-full bg-white transition-transform duration-300 z-10 transform data-[state=checked]:translate-x-[60px]"
                    /> */}
                  {/* </Switch.Root> */}
                  {/* </UmamiTrack> */}
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 flex-shrink-0">
                    <Users className="h-3 w-3" />
                  </Button>
                  
                  <UmamiTrack event={UmamiEvents.AGENT_CHAT_ADD_FLOW_BUTTON} includeUserData={false}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 w-6 p-0 text-[#03DAC6] hover:bg-[#03DAC6] hover:bg-opacity-20 flex-shrink-0" 
                    onClick={handleAddFlowClick}
                    title="Add new chat from flow"
                    >
                    <Plus className="h-3 w-3" />
                  </Button>
                  </UmamiTrack>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-grow">
              {chatSessions.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  No chat sessions available
                </div>
              ) : (
                <div className="h-full max-h-[75vh] overflow-y-auto py-2">
                  {chatSessions.map((session) => (
                    <motion.div
                      key={session.id}
                      className={`group px-4 py-3 border-l-2 cursor-pointer ${
                        selectedSession?.id === session.id
                          ? "border-[hsl(var(--primary))] bg-primary/20"
                          : "border-transparent hover:bg-background-surface"
                      } ${
                        !session.blueprintExists || session.isSharingDisabled
                          ? "opacity-50 bg-gray-800/30" 
                          : ""
                      }`}
                      onClick={() => handleSessionSelect(session)}
                      whileHover={{ x: 2 }}
                      transition={{ duration: 0.1 }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center min-w-0 flex-1">
                          <MessageSquare className="h-4 w-4 mr-2 text-gray-400 flex-shrink-0" />
                          <span className="text-sm font-medium truncate">
                            {session.title}
                          </span>
                        </div>
                        <UmamiTrack event={UmamiEvents.AGENT_CHAT_DELETE_CHAT_BUTTON} includeUserData={false}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteChat(session, e)}
                          >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                        </UmamiTrack>
                      </div>
                      <div className="mt-1 flex items-center text-xs text-gray-400">
                        <Clock className="h-3 w-3 mr-1" />
                        <span>{session.lastActive}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500 truncate">
                        {session.preview}
                      </p>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* First Resizable divider */}
        <div
          className={`w-1 cursor-col-resize transition-colors duration-200 flex-shrink-0 ${
            isResizing && activeResizer === 'left' ? 'opacity-100' : 'opacity-50'
          }`}
          style={{
            backgroundColor: 'hsl(var(--primary))',
          }}
          onMouseDown={handleMouseDown('left')}
          title="Drag to resize panels"
        />

        {/* ChatInterface Area - Always mounted, hidden when in graph mode to preserve streaming state */}
        <motion.div 
          key="chat-panel"
          initial={false}
          animate={{ 
            opacity: carouselMode === 'graph' ? 0 : 1,
            x: carouselMode === 'graph' ? -30 : 0,
            scale: carouselMode === 'graph' ? 0.98 : 1
          }}
          transition={{ 
            type: "spring", 
            stiffness: 300, 
            damping: 30,
            duration: 0.4 
          }}
          className="flex-shrink-0 flex flex-col"
          style={{ 
            width: carouselMode === 'graph' ? 0 : `${chatInterfaceWidth}%`,
            overflow: carouselMode === 'graph' ? 'hidden' : 'visible',
            pointerEvents: carouselMode === 'graph' ? 'none' : 'auto',
            // Carousel-like width transition
            transition: carouselMode === 'chat' 
              ? 'width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease-out'
              : 'width 0.4s ease-out, opacity 0.3s ease-out'
          }}
        >
          <div className="flex-grow">
            {isLoadingSessionMessages ? (
              <SessionMessagesLoader />
            ) : (
              <ChatInterface
                key={selectedSession?.id || 'no-session'}
                runId={selectedSession?.id || ''}
                triggerExecution={triggerExecution}
                initialMessages={currentSessionMessages}
                blueprintExists={selectedSession?.blueprintExists ?? true}
                isSharingDisabled={isSharingDisabled}
                blueprintValid={isBlueprintValid}
                isValidatingBlueprint={isValidatingBlueprint}
                isBlueprintGraphHidden={carouselMode === 'chat'}
                isChatOnlyMode={isChatOnlyMode}
                onSetCarouselMode={handleSetCarouselMode}
                carouselMode={carouselMode}
                isLiveRequest={isLiveRequest}
              />
            )}
          </div>
          
          {/* ExecutionStream - conditionally rendered within ChatInterface area */}
          {selectedSession && showExecutionStream && (
            <div className="h-1/3 border-t border-gray-800 mt-2">
              <ExecutionStream
                blueprintId={selectedSession.blueprintId}
                isLiveRequest={isLiveRequest}
              />
            </div>
          )}
        </motion.div>

        {/* Second Resizable divider - only show when both panels are visible (normal mode) */}
        {/* For chat-only sessions: always show (displays message). For regular: show in normal mode */}
        {(isChatOnlyMode || carouselMode === 'normal') && (
          <div
            className={`w-1 transition-colors duration-200 flex-shrink-0 ${
              isChatOnlyMode ? 'cursor-default' : 'cursor-col-resize'
            } ${
              isResizing && activeResizer === 'right' ? 'opacity-100' : 'opacity-50'
            }`}
            style={{
              backgroundColor: 'hsl(var(--primary))',
            }}
            onMouseDown={isChatOnlyMode ? undefined : handleMouseDown('right')}
            title={isChatOnlyMode ? "Workflow not available for chat-only sessions" : "Drag to resize panels"}
          />
        )}

        {/* Blueprint Graph Visualization or Chat-Only Message - Always mounted, hidden when in chat mode to preserve node state */}
        <motion.div 
          key="graph-panel"
          initial={false}
          animate={{ 
            opacity: (!isChatOnlyMode && carouselMode === 'chat') ? 0 : 1,
            x: (!isChatOnlyMode && carouselMode === 'chat') ? 30 : 0,
            scale: (!isChatOnlyMode && carouselMode === 'chat') ? 0.98 : 1
          }}
          transition={{ 
            type: "spring", 
            stiffness: 300, 
            damping: 30,
            duration: 0.4 
          }}
          className="flex-shrink-0" 
          style={{ 
            width: (!isChatOnlyMode && carouselMode === 'chat') ? 0 : `${blueprintGraphWidth}%`,
            overflow: (!isChatOnlyMode && carouselMode === 'chat') ? 'hidden' : 'visible',
            pointerEvents: (!isChatOnlyMode && carouselMode === 'chat') ? 'none' : 'auto',
            // Carousel-like width transition
            transition: carouselMode === 'graph' 
              ? 'width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease-out'
              : 'width 0.4s ease-out, opacity 0.3s ease-out'
          }}
        >
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col ml-0 relative">
            {/* Carousel mode switch - shown when in graph-only mode */}
            {carouselMode === 'graph' && !isChatOnlyMode && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3, duration: 0.2 }}
                className="absolute top-3 right-3 z-10"
              >
                <div className="flex items-center bg-background-surface border border-gray-700 rounded-lg p-0.5 shadow-lg">
                  {/* Split View - not selected in graph mode */}
                  <button
                    onClick={() => handleSetCarouselMode('normal')}
                    className="p-1.5 rounded-md transition-all duration-200 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
                    title="Split View"
                  >
                    <Columns3 className="h-4 w-4" />
                  </button>
                  {/* Full Chat View - not selected in graph mode */}
                  <button
                    onClick={() => handleSetCarouselMode('chat')}
                    className="p-1.5 rounded-md transition-all duration-200 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
                    title="Full Chat View"
                  >
                    <MessageSquare className="h-4 w-4" />
                  </button>
                  {/* Full Graph View - always selected in graph mode */}
                  <button
                    onClick={() => handleSetCarouselMode('graph')}
                    className="p-1.5 rounded-md transition-all duration-200 bg-primary text-white shadow-sm"
                    title="Full Graph View"
                  >
                    <Network className="h-4 w-4" />
                  </button>
                </div>
              </motion.div>
            )}
            {/* TODO: Add below general component that gets 'blueprintId' and showing his title and uid - can be called from multiple places */}
            {/* <CardHeader className="py-3 px-4 border-b border-gray-800">
              {selectedSession && (
                  <div className="mb-4 px-4 py-3 bg-[#8A2BE2] bg-opacity-10 border border-[hsl(var(--primary))] rounded-md">
                    <p className="text-sm">
                      <span className="font-medium">Active Graph:</span> {''} <span className="text-xs text-gray-400 ml-2">(ID: {selectedSession.blueprintId || 'N/A'})</span>
                    </p>
                  </div>
                )}
              {selectedSession && (
                <p className="text-xs text-gray-400 mt-1">
                  Blueprint ID: {selectedSession.blueprintId || 'N/A'}
                </p>
              )}
            </CardHeader> */}
            <CardContent className="p-0 flex-grow">
              {isChatOnlyMode ? (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm flex-col p-6">
                  <p className="mb-2 text-base">This session was created from a shared chat link</p>
                  <p className="text-xs text-gray-500 mb-1">
                    Workflow: <span className="font-medium text-gray-300">
                      {selectedSession?.blueprintName || "Unknown"}
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Workflow details are not available in shared link sessions</p>
                  {selectedSession?.isSharingDisabled && (
                    <div className="mt-4 p-3 bg-red-900/20 border border-red-800 rounded-md">
                      <p className="text-xs text-red-400">Chat sharing has been disabled for this workflow</p>
                    </div>
                  )}
                </div>
              ) : selectedSession?.blueprintId ? (
                <GraphDisplay
                  key={`main-graph-${selectedSession.id}`}
                  blueprintId={selectedSession.blueprintId}
                  specDict={blueprintSpecCache.get(selectedSession.blueprintId)}
                  height="100%"
                  showBackground={true}
                  interactive={true}
                  centerInView={true}
                  animated={true}
                  validationResults={blueprintValidationResults}
                  isValidating={isValidatingBlueprint}
                  isLiveRequest={isLiveRequest}
                  isGraphVisible={carouselMode !== 'chat'}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                  {selectedSession ? 'No blueprint available for this session' : 'Select a chat session to view blueprint'}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Add Flow Modal */}
      <Dialog open={showAddFlowModal} onOpenChange={setShowAddFlowModal}>
        <CustomDialogContent 
          className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden"
        >
          <DialogHeader className="flex-shrink-0 pb-4">
            <DialogTitle className="text-lg">Add New Chat from Flow</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-hidden">
            <div key={`new-chat-graph-${showAddFlowModal}`}>
              <WorkflowsPanel
                selectedFlow={selectedFlowForModal}
                onFlowSelect={handleFlowSelect}
                showActiveStatus={false}
                showDeleteButton={false}
                height="100%"
                graphProps={{
                  showBackground: true,
                  interactive: true,
                }}
              />
            </div>
          </div>
          <DialogFooter className="flex-shrink-0 pt-4 border-t border-gray-800">
            <Button
              variant="outline"
              onClick={handleCancelAddFlow}
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
              {isCreatingSession ? "Creating..." : "Add"}
            </Button>
          </DialogFooter>
        </CustomDialogContent>
      </Dialog>

      {/* Delete Chat Confirmation Modal */}
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{chatToDelete?.title}"?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel 
              onClick={cancelDeleteChat}
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
    </div>
  );
}