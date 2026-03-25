import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Trash2, Loader2, Sparkles, Info, Copy, RotateCcw, ThumbsUp, ThumbsDown, Check, Columns3, MessageSquare, Network, Maximize2, Minimize2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "../../../http/axiosAgentConfig";
import { MarkdownComponents, preprocessText } from "./helpers/TextComponents";
import { SessionPayload } from "../ExecutionTab";
import { useStreamingData } from "../StreamingDataContext";
import { Message, StreamLogEntry, WorkPlanSnapshot } from "./types";
import { StreamLogDisplay } from "./StreamLogDisplay";
import { useToast } from "@/hooks/use-toast";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import WorkflowStatusBanner, { WorkflowBannerMessages } from '@/components/shared/WorkflowStatusBanner';


// Backend message format
interface BackendMessage {
  content: string;
  role: "user" | "assistant";
}

interface ChatInterfaceProps {
  runId?: string;
  triggerExecution: (sessionPayload: SessionPayload) => Promise<string>;
  initialMessages?: BackendMessage[];
  blueprintExists?: boolean;
  isSharingDisabled?: boolean; // If true, sharing is disabled for this blueprint
  blueprintValid?: boolean;
  isValidatingBlueprint?: boolean;
  isBlueprintGraphHidden?: boolean;
  isChatOnlyMode?: boolean; // If true, hide agent thinking and workflow details
  onSetCarouselMode?: (mode: 'normal' | 'chat' | 'graph') => void; // Carousel mode setter
  carouselMode?: 'normal' | 'chat' | 'graph'; // Current carousel mode
  isLiveRequest?: boolean; // True when session is actively streaming (including reconnection)
}

export default function ChatInterface({
  runId,
  triggerExecution,
  initialMessages = [],
  blueprintExists = true,
  isSharingDisabled = false,
  blueprintValid = true,
  isValidatingBlueprint = false,
  isBlueprintGraphHidden = false,
  isChatOnlyMode = false,
  onSetCarouselMode,
  carouselMode = 'normal',
  isLiveRequest = false,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [currentStreamingMessageId, setCurrentStreamingMessageId] = useState<
    string | null
  >(null);
  const [workPlanData, setWorkPlanData] = useState<Record<string, WorkPlanSnapshot[]>>({});
  const [streamLogData, setStreamLogData] = useState<Record<string, StreamLogEntry[]>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const workplanStreamingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const workPlanDataRef = useRef<Record<string, WorkPlanSnapshot[]>>({});
  const streamLogDataRef = useRef<Record<string, StreamLogEntry[]>>({});
  const { nodeListRef, clearStream } = useStreamingData();
  const { toast } = useToast();
  const [userPromptsMap, setUserPromptsMap] = useState<Record<string, string>>({});
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  // ────────────────────────────────────────────────────────────────────────────────
  // Auto-expanding textarea configuration
  // ────────────────────────────────────────────────────────────────────────────────
  const TEXTAREA_MIN_HEIGHT = 44;  // Starting height (single line + padding)
  const TEXTAREA_MAX_HEIGHT = 200; // Maximum expansion height (normal mode)
  
  const getExpandedHeight = useCallback(() => {
    return Math.floor(window.innerHeight * 0.65);
  }, []);
  
  const [isAtMaxHeight, setIsAtMaxHeight] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  /**
   * Adjusts textarea height dynamically based on content.
   * Resets to minimum when empty, expands up to max as content grows.
   */
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // If in expanded mode, use 80% of viewport height
    if (isExpanded) {
      textarea.style.height = `${getExpandedHeight()}px`;
      textarea.style.overflowY = 'auto';
      return;
    }

    // If content is empty, reset to minimum height immediately
    if (!textarea.value || textarea.value.trim() === '') {
      textarea.style.height = `${TEXTAREA_MIN_HEIGHT}px`;
      textarea.style.overflowY = 'hidden';
      setIsAtMaxHeight(false);
      return;
    }

    // Reset height to 'auto' to get accurate scrollHeight measurement
    textarea.style.height = 'auto';
    
    // Calculate new height based on content
    const scrollHeight = textarea.scrollHeight;
    const newHeight = Math.min(Math.max(scrollHeight, TEXTAREA_MIN_HEIGHT), TEXTAREA_MAX_HEIGHT);
    
    textarea.style.height = `${newHeight}px`;
    
    // Track if we've reached max height (for expand icon)
    const reachedMax = scrollHeight > TEXTAREA_MAX_HEIGHT;
    setIsAtMaxHeight(reachedMax);
    
    // Enable scrolling only when content exceeds max height
    textarea.style.overflowY = reachedMax ? 'auto' : 'hidden';
  }, [isExpanded, getExpandedHeight]);

  /**
   * Resets textarea to initial compact state
   */
  const resetTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    textarea.style.height = `${TEXTAREA_MIN_HEIGHT}px`;
    textarea.style.overflowY = 'hidden';
    setIsAtMaxHeight(false);
    setIsExpanded(false);
  }, []);

  /**
   * Toggles between normal and expanded textarea height
   */
  const toggleExpandedHeight = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  /**
   * Returns the appropriate placeholder text for the chat input based on current state.
   * Priority order: deleted > sharing disabled > validating > invalid > default
   */
  const getInputPlaceholder = useCallback((): string => {
    if (!blueprintExists) {
      return "This chat cannot be continued - workflow was deleted";
    }
    if (isSharingDisabled) {
      return "Chat sharing has been disabled for this workflow";
    }
    if (isValidatingBlueprint) {
      return "Validating workflow...";
    }
    if (!blueprintValid) {
      return "This chat cannot be continued - workflow validation failed";
    }
    return "Ask a question about your data...";
  }, [blueprintExists, isSharingDisabled, isValidatingBlueprint, blueprintValid]);

  // Transform backend messages to frontend format (streamLogs/workPlans, managed separately)
  const transformBackendMessagesToFrontend = useCallback(
    (backendMessages: BackendMessage[]): Message[] => {
      return backendMessages.map((msg, index) => ({
        id: `${Date.now()}-${index}`,
        content: msg.content,
        sender: msg.role === "user" ? "user" : "ai",
        // For AI messages, we might want to add finalAnswer if it's the last assistant message
        ...(msg.role === "assistant" && {
          finalAnswer: msg.content,
        }),
      }));
    },
    [],
  );

  // Initialize messages from props or default
  useEffect(() => {
    if (initialMessages && initialMessages.length > 0) {
      const transformedMessages =
        transformBackendMessagesToFrontend(initialMessages);
      setMessages(transformedMessages);
    } else {
      // Default welcome message when no initial messages
      setMessages([
        {
          id: "welcome",
          content:
            "Hello! I'm your AI assistant. How can I help you process your data today?",
          sender: "ai",
        },
      ]);
    }
  }, [initialMessages, transformBackendMessagesToFrontend]);

  // useEffect(() => {
  //   scrollToBottom();
  // }, [messages]);

  // Adjust textarea height when input or expanded state changes
  useEffect(() => {
    adjustTextareaHeight();
  }, [inputMessage, isExpanded, adjustTextareaHeight]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Map stream type to status
  const mapStreamToStatus = (
    stream: string,
  ): "processing" | "complete" | "error" => {
    switch (stream) {
      case "PROGRESS":
        return "processing";
      case "ERROR":
        return "error";
      case "COMPLETE":
        return "complete";
      default:
        return "processing";
    }
  };

  // Optimized streaming logic for stream logs using separate state (no messages updates)
  const startStreamingLogs = (messageId: string) => {
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
    }

    let lastUpdateTime = 0;
    const UPDATE_THROTTLE = 100; // Update frequency to 100ms

    streamingIntervalRef.current = setInterval(() => {
      const now = Date.now();
      if (now - lastUpdateTime < UPDATE_THROTTLE) {
        return;
      }

      const list = Array.from(nodeListRef.current.values());

      if (list.length > 0) {
        lastUpdateTime = now;

        const currentLogs = streamLogDataRef.current[messageId] || [];
        const updatedStreamLogs: StreamLogEntry[] = [];

        // Process each entry from nodeListRef for stream logs only
        list.forEach((entry) => {
          // Process stream logs
          const existingLog = currentLogs.find(
            (log) => log.nodeId === entry.node_name,
          );

          // Only update if there's actually a change
          const newStatus = mapStreamToStatus(entry.stream);
          const newMessage = entry.text;

          if (
            !existingLog ||
            existingLog.status !== newStatus ||
            existingLog.message !== newMessage
          ) {
            // Show stream log if there's text content OR if there are tool calls
            if (newMessage || (entry?.tools && entry.tools.length > 0)) {
              updatedStreamLogs.push({
                nodeId: entry.node_name,
                nodeName: entry.node_name
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (l: string) => l.toUpperCase()),
                message: newMessage || "", // Allow empty message when showing tools
                tools: entry?.tools || [],
                status: newStatus,
                isExpanded: existingLog?.isExpanded || false,
              });
            }
          } else {
            // Keep existing log unchanged
            updatedStreamLogs.push(existingLog);
          }
        });

        // Only update if there are actual changes
        const hasLogChanges =
          updatedStreamLogs.length !== currentLogs.length ||
          updatedStreamLogs.some((log, index) => {
            const currentLog = currentLogs[index];
            return (
              !currentLog ||
              log.status !== currentLog.status ||
              log.message !== currentLog.message
            );
          });

        if (hasLogChanges) {
          // Update the ref and state
          streamLogDataRef.current = {
            ...streamLogDataRef.current,
            [messageId]: updatedStreamLogs
          };
          
          setStreamLogData(prev => ({
            ...prev,
            [messageId]: updatedStreamLogs
          }));
        }
      }
    }, 100); // Check every 100ms but only update every 300ms
  };

  // Separate streaming logic for workplans with 500ms intervals using dedicated state
  const startStreamingWorkPlans = (messageId: string) => {
    if (workplanStreamingIntervalRef.current) {
      clearInterval(workplanStreamingIntervalRef.current);
    }

    workplanStreamingIntervalRef.current = setInterval(() => {
      const list = Array.from(nodeListRef.current.values());

      if (list.length > 0) {
        const currentWorkPlans = workPlanDataRef.current[messageId] || [];
        const updatedWorkPlans: WorkPlanSnapshot[] = [];

        // Process each entry from nodeListRef for workplans only
        list.forEach((entry) => {
          // Process workplan data
          if (entry.workplans && entry.workplans.length > 0) {
            entry.workplans.forEach((workplanSnapshot: WorkPlanSnapshot) => {
              const existingPlanIndex = updatedWorkPlans.findIndex(
                (wp) => wp.plan_id === workplanSnapshot.plan_id
              );

              if (existingPlanIndex !== -1) {
                // Update existing workplan while preserving expansion state
                const existingPlan = updatedWorkPlans[existingPlanIndex];
                updatedWorkPlans[existingPlanIndex] = {
                  ...workplanSnapshot,
                  isExpanded: existingPlan.isExpanded // Preserve expansion state
                };
              } else {
                // Add new workplan with default expansion state
                updatedWorkPlans.push({
                  ...workplanSnapshot,
                  isExpanded: false // Default to collapsed
                });
              }
            });
          }
        });

        // Also preserve existing workplans that weren't updated
        currentWorkPlans.forEach((existingPlan) => {
          if (!updatedWorkPlans.find(wp => wp.plan_id === existingPlan.plan_id)) {
            updatedWorkPlans.push(existingPlan);
          }
        });

        // More precise workplan change detection to reduce flickering
        const hasPlanChanges = (() => {
          if (updatedWorkPlans.length !== currentWorkPlans.length) {
            return true; // Number of plans changed
          }

          for (const updatedPlan of updatedWorkPlans) {
            const currentPlan = currentWorkPlans.find(p => p.plan_id === updatedPlan.plan_id);
            
            if (!currentPlan) {
              return true; // New plan
            }

            // Check if plan-level properties changed
            if (updatedPlan.action !== currentPlan.action ||
                updatedPlan.workplan.summary !== currentPlan.workplan.summary) {
              return true;
            }

            // Check work items for meaningful changes
            const updatedItems = Object.values(updatedPlan.workplan.items);
            const currentItems = Object.values(currentPlan.workplan.items);

            if (updatedItems.length !== currentItems.length) {
              return true; // Number of items changed
            }

            // Check each item for status or content changes
            for (const updatedItem of updatedItems) {
              const currentItem = currentItems.find(item => item.id === updatedItem.id);
              
              if (!currentItem) {
                return true; // New item
              }

              // Only trigger update for meaningful changes
              if (
                currentItem.status !== updatedItem.status ||
                currentItem.title !== updatedItem.title ||
                currentItem.description !== updatedItem.description ||
                currentItem.error !== updatedItem.error ||
                currentItem.retry_count !== updatedItem.retry_count
              ) {
                return true;
              }
            }
          }

          return false; // No meaningful changes
        })();

        if (hasPlanChanges) {
          // Update the ref and state
          workPlanDataRef.current = {
            ...workPlanDataRef.current,
            [messageId]: updatedWorkPlans
          };
          
          setWorkPlanData(prev => ({
            ...prev,
            [messageId]: updatedWorkPlans
          }));
        }
      }
    }, 500); // Check every 500ms for workplans
  };

  // Stop streaming logs and workplans and mark all as complete
  const stopStreamingLogs = (messageId?: string) => {
    // Clear stream logs interval
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
      streamingIntervalRef.current = null;
    }

    // Clear workplan streaming interval
    if (workplanStreamingIntervalRef.current) {
      clearInterval(workplanStreamingIntervalRef.current);
      workplanStreamingIntervalRef.current = null;
    }

    // Mark all processing nodes as complete when streaming stops
    const targetMessageId = messageId || currentStreamingMessageId;
    if (targetMessageId) {
      const currentLogs = streamLogDataRef.current[targetMessageId] || [];
      const updatedLogs = currentLogs.map((log) => ({
        ...log,
        status: log.status === "processing" ? "complete" : log.status,
      }));
      
      if (updatedLogs.length > 0) {
        streamLogDataRef.current = {
          ...streamLogDataRef.current,
          [targetMessageId]: updatedLogs
        };
        
        setStreamLogData(prev => ({
          ...prev,
          [targetMessageId]: updatedLogs
        }));
      }
    }
  };

  // Ref to track if current streaming was initiated by reconnection (not handleSendMessage)
  const isReconnectionStreamRef = useRef(false);

  // Handle reconnection to active stream (when user navigates back to a running session)
  // With the key prop on ChatInterface, each session gets a fresh component instance.
  // 
  // This effect watches BOTH isLiveRequest AND messages because:
  // 1. isLiveRequest might become true AFTER mount (via checkAndReconnect)
  // 2. messages are set AFTER mount (via initialMessages useEffect)
  // Both conditions must be met to start polling.
  //
  // This recreates the same behavior as triggerExecution:
  // - triggerExecution: handleSendMessage starts polling, then triggerExecution fills nodeListRef
  // - Reconnection: checkAndReconnect fills nodeListRef via Redis, this effect starts polling
  useEffect(() => {
    // Skip if already streaming (user-initiated via handleSendMessage)
    if (currentStreamingMessageId) return;
    // Skip if user is typing (middle of handleSendMessage)
    if (isTyping) return;
    
    // Start polling when session is live and messages are loaded
    if (isLiveRequest && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      
      // If the last message is from the user, the AI response is still being generated
      // We need to create a placeholder AI message to attach the stream to
      // (This mirrors what handleSendMessage does when user sends a message)
      // During a live stream, the last message is always USER because:
      // - User Q is saved immediately when sent
      // - AI response is saved only when stream completes (with finalAnswer)
      // If last message is AI, stream has already completed - no reconnection needed
      if (lastMessage.sender === 'user') {
        const reconnectMessageId = `reconnect-${Date.now()}`;
        const placeholderAiMessage: Message = {
          id: reconnectMessageId,
          content: "",
          sender: "ai",
        };
        
        // Add placeholder AI message
        setMessages((prev) => [...prev, placeholderAiMessage]);
        
        // Mark this as a reconnection stream (not user-initiated)
        isReconnectionStreamRef.current = true;
        setCurrentStreamingMessageId(reconnectMessageId);
        startStreamingLogs(reconnectMessageId);
        startStreamingWorkPlans(reconnectMessageId);
      }
    }
  }, [isLiveRequest, messages]);

  // Handle stream end from parent (when isLiveRequest becomes false)
  // For reconnection streams, fetch the final answer since handleSendMessage isn't running
  useEffect(() => {
    if (!isLiveRequest && currentStreamingMessageId) {
      const messageId = currentStreamingMessageId;
      const wasReconnection = isReconnectionStreamRef.current;
      
      // Stop polling
      stopStreamingLogs(messageId);
      setCurrentStreamingMessageId(null);
      isReconnectionStreamRef.current = false;
      
      // For reconnection streams, fetch the final answer
      if (wasReconnection && runId) {
        (async () => {
          try {
            const response = await axios.get(`/sessions/session.chat.get?sessionId=${runId}`);
            const finalAnswer = response.data?.output;
            
            if (finalAnswer) {
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === messageId) {
                    return { ...msg, finalAnswer };
                  }
                  return msg;
                })
              );
            }
          } catch (error) {
            console.error('Error fetching final state after reconnection:', error);
          }
        })();
      }
    }
  }, [isLiveRequest, runId]);

  // Toggle expansion of a specific node log in separate state
  const toggleNodeExpansion = useCallback((messageId: string, nodeId: string) => {
    const currentLogs = streamLogDataRef.current[messageId] || [];
    const updatedLogs = currentLogs.map((log) =>
      log.nodeId === nodeId
        ? { ...log, isExpanded: !log.isExpanded }
        : log,
    );
    
    streamLogDataRef.current = {
      ...streamLogDataRef.current,
      [messageId]: updatedLogs
    };
    
    setStreamLogData(prev => ({
      ...prev,
      [messageId]: updatedLogs
    }));
  }, []);

  // Toggle expansion of a specific workplan in separate state
  const toggleWorkPlanExpansion = useCallback((messageId: string, planId: string) => {
    const currentPlans = workPlanDataRef.current[messageId] || [];
    const updatedPlans = currentPlans.map((plan) =>
      plan.plan_id === planId
        ? { ...plan, isExpanded: !plan.isExpanded }
        : plan,
    );
    
    workPlanDataRef.current = {
      ...workPlanDataRef.current,
      [messageId]: updatedPlans
    };
    
    setWorkPlanData(prev => ({
      ...prev,
      [messageId]: updatedPlans
    }));
  }, []);


  // User sends message → Creates an AI message with empty streamLogs
  // Streaming starts → Interval polls for node updates and updates the message
  // Live updates → Each node appears/updates as data becomes available
  // User interaction → Can expand/collapse individual node logs
  // Completion → Final answer appears and streaming stops
  // Cleanup → All intervals are properly cleared
  const handleSendMessage = async (messageToSend?: string) => {
    const messageContent = messageToSend || inputMessage;
    if (messageContent.trim() === "") return;

    // Check if flow is loaded (runId should not be empty or null)
    if (!runId || runId.trim() === "") {
      toast({
        title: "No Flow Loaded",
        description: "You must load an existing flow before you can start chatting with the AI assistant.",
        variant: "destructive",
      });
      return;
    }

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageContent,
      sender: "user",
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsTyping(true);

    // Reset textarea to compact state and focus
    setTimeout(() => {
      resetTextareaHeight();
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(0, 0);
      }
    }, 0);

    // Create initial AI message for streaming (no streamLogs, managed separately)
    const streamingMessageId = (Date.now() + 1).toString();
    const initialAiMessage: Message = {
      id: streamingMessageId,
      content: "",
      sender: "ai",
    };

    setMessages((prev) => [...prev, initialAiMessage]);
    clearStream();
    setCurrentStreamingMessageId(streamingMessageId);

    setUserPromptsMap(prev => ({
      ...prev,
      [streamingMessageId]: messageContent
    }));

    // Start streaming logs and workplans
    startStreamingLogs(streamingMessageId);
    startStreamingWorkPlans(streamingMessageId);

    try {
      const sessionPayload: SessionPayload = {
        sessionId: runId || "",
        inputs: { user_prompt: messageContent },
        scope: "public",
        loggedInUser: "default",
      };

      const response = await triggerExecution(sessionPayload);

      // Update the message with final answer
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === streamingMessageId) {
            return {
              ...msg,
              finalAnswer: response,
            };
          }
          return msg;
        }),
      );
    } catch (error) {
      console.error("Error in chat interaction:", error);

      // Update with error message
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === streamingMessageId) {
            return {
              ...msg,
              finalAnswer:
                "I'm sorry, there was an error processing your request.",
            };
          }
          return msg;
        }),
      );
    } finally {
      setIsTyping(false);
      stopStreamingLogs(streamingMessageId);
      setCurrentStreamingMessageId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { // Allow Shift+Enter for new lines
      e.preventDefault(); // Prevent default Enter behavior (new line)
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "cleared",
        content: "Chat cleared. How can I help you with your data pipeline?",
        sender: "ai",
      },
    ]);
    // Clear both workplan and stream log data
    setWorkPlanData({});
    workPlanDataRef.current = {};
    setStreamLogData({});
    streamLogDataRef.current = {};
    setUserPromptsMap({});
    setCopiedMessageId(null);
    stopStreamingLogs();
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      stopStreamingLogs();
    };
  }, []);

  // Memoized typing indicator
  const TypingIndicator = useMemo(
    () => (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="bg-background-dark border border-gray-800 rounded-2xl rounded-tl-none p-3 max-w-[80%]">
          {/* AI-generated indicator for typing state */}
          <div 
            className="mb-2.5 pb-2 border-b border-gray-700/30"
            role="status"
            aria-label="AI-generated content"
          >
            <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border" style={{ borderColor: `hsl(var(--primary) / 0.3)` }}>
              <Sparkles 
                className="h-3.5 w-3.5" 
                style={{ color: `hsl(var(--primary) / 0.85)` }}
                aria-hidden="true" 
              />
              <span className="text-xs font-medium text-gray-300/90 tracking-wide">
                AI Generated
              </span>
            </div>
          </div>
          <div className="flex space-x-1">
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
              }}
            />
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
                delay: 0.1,
              }}
            />
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
                delay: 0.2,
              }}
            />
          </div>
        </div>
      </motion.div>
    ),
    [],
  );

  // Loader for chat-only mode (simpler, cleaner loader)
  const ChatOnlyLoader = useMemo(
    () => (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="bg-background-dark border border-gray-800 rounded-2xl rounded-tl-none p-4 max-w-[80%]">
          <div className="flex items-center space-x-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm text-gray-400">Processing your request...</span>
          </div>
        </div>
      </motion.div>
    ),
    [],
  );

  // Component for AI message action buttons
  const MessageActions = ({ message }: { message: Message }) => {
    const handleCopy = async () => {
      if (message.finalAnswer) {
        try {
          await navigator.clipboard.writeText(message.finalAnswer);
          setCopiedMessageId(message.id);
          setTimeout(() => setCopiedMessageId(null), 2000);
        } catch (error) {
          console.error("Failed to copy:", error);
          toast({
            title: "Copy failed",
            description: "Failed to copy to clipboard",
            variant: "destructive",
          });
        }
      }
    };

    const handleTryAgain = async () => {
      const originalPrompt = userPromptsMap[message.id];
      if (!originalPrompt) {
        toast({
          title: "Error",
          description: "Could not find original prompt",
          variant: "destructive",
        });
        return;
      }

      // Directly send the message with the original prompt
      await handleSendMessage(originalPrompt);
    };

    const isCopied = copiedMessageId === message.id;

    return (
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-gray-700/30">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          disabled={!message.finalAnswer}
          className="h-7 px-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
          title="Copy response"
        >
          {isCopied ? (
            <Check className="h-3.5 w-3.5 mr-1.5" />
          ) : (
            <Copy className="h-3.5 w-3.5 mr-1.5" />
          )}
          <span className="text-xs">{isCopied ? "Copied!" : "Copy"}</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleTryAgain}
          disabled={!userPromptsMap[message.id] || isTyping}
          className="h-7 px-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
          title="Try again with the same prompt"
        >
          <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Try Again</span>
        </Button>

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-gray-400 hover:text-green-400 hover:bg-gray-800/50"
          title="Good response"
        >
          <ThumbsUp className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Good</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-gray-400 hover:text-red-400 hover:bg-gray-800/50"
          title="Bad response"
        >
          <ThumbsDown className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Bad</span>
        </Button>
      </div>
    );
  };

  // Component for rendering message content with markdown support
  const MessageContent = ({ message }: { message: Message }) => {
    // Get stream logs and workplans from separate states
    const streamLogs = streamLogData[message.id] || [];
    const workPlans = workPlanData[message.id] || [];

    // Memoize the complete message object with separate data
    const messageWithStreamingData = useMemo(() => {
      // Create enhanced message object only when needed
      if (streamLogs.length > 0 || workPlans.length > 0) {
        return {
          ...message,
          streamLogs: streamLogs,
          workPlans: workPlans
        };
      }
      
      return message;
    }, [message, streamLogs, workPlans]);

    if (message.sender === "user") {
      return (
        <div className="text-sm whitespace-pre-line">{message.content}</div>
      );
    }

    if (
      message.sender === "ai" &&
      (streamLogs.length > 0 || workPlans.length > 0 || message.finalAnswer)
    ) {
      return (
        <div className="space-y-3 w-full">
          {/* Stream logs display - hidden in chat-only mode */}
          {!isChatOnlyMode && (
            <StreamLogDisplay
              message={messageWithStreamingData}
              onToggleExpansion={toggleNodeExpansion}
              onToggleWorkPlanExpansion={toggleWorkPlanExpansion}
            />
          )}

          {/* Final answer with markdown rendering */}
          {message.finalAnswer && (
            <div
              className="mt-3 p-3 rounded-lg"
              style={{
                // backgroundColor: `hsl(var(--primary) / 0.1)`,
                border: `1px solid hsl(var(--primary) / 0.3)`,
              }}
            >
              <div className="text-sm text-gray-100">
                <ReactMarkdown
                  components={MarkdownComponents}
                  remarkPlugins={[remarkGfm]}
                >
                  {preprocessText(message.finalAnswer)}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      );
    }

    // Default AI message without streaming
    return (
      <div className="text-sm">
        <ReactMarkdown
          components={MarkdownComponents}
          remarkPlugins={[remarkGfm]}
        >
          {preprocessText(message.content)}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <Card className="bg-background-card shadow-card border-gray-800 flex flex-col h-full max-h-[82.5vh]">
      <CardHeader className="py-4 px-6 flex flex-row justify-between items-center flex-shrink-0">
        <CardTitle className="text-lg font-heading">AI Assistant</CardTitle>
        <div className="flex space-x-1 items-center">
          {!isChatOnlyMode && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearChat}
                className="text-gray-400 hover:text-gray-100"
                title="Clear chat"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
              {/* Carousel Mode Switch - 3 icons for Split/Chat/Graph views */}
              {onSetCarouselMode && !isChatOnlyMode && (
                <div className="flex items-center bg-background-surface border border-gray-700 rounded-lg p-0.5">
                  {/* Split View */}
                  <button
                    onClick={() => onSetCarouselMode('normal')}
                    className={`p-1.5 rounded-md transition-all duration-200 ${
                      carouselMode === 'normal'
                        ? 'bg-primary text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
                    }`}
                    title="Split View"
                  >
                    <Columns3 className="h-4 w-4" />
                  </button>
                  {/* Full Chat View */}
                  <button
                    onClick={() => onSetCarouselMode('chat')}
                    className={`p-1.5 rounded-md transition-all duration-200 ${
                      carouselMode === 'chat'
                        ? 'bg-primary text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
                    }`}
                    title="Full Chat View"
                  >
                    <MessageSquare className="h-4 w-4" />
                  </button>
                  {/* Full Graph View */}
                  <button
                    onClick={() => onSetCarouselMode('graph')}
                    className={`p-1.5 rounded-md transition-all duration-200 ${
                      carouselMode === 'graph'
                        ? 'bg-primary text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
                    }`}
                    title="Full Graph View"
                  >
                    <Network className="h-4 w-4" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[90%] rounded-2xl p-3 ${
                    message.sender === "user"
                      ? "bg-primary text-white rounded-tr-none"
                      : "bg-background-dark border border-gray-800 rounded-tl-none"
                  }`}
                >
                  {/* AI-generated indicator inside message bubble */}
                  {message.sender === "ai" && (
                    <div 
                      className="mb-2.5 pb-2 border-b border-gray-700/30"
                      role="status"
                      aria-label="AI-generated content"
                    >
                      <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border" style={{ borderColor: `hsl(var(--primary) / 0.3)` }}>
                        <Sparkles 
                          className="h-3.5 w-3.5" 
                          style={{ color: `hsl(var(--primary) / 0.85)` }}
                          aria-hidden="true" 
                        />
                        <span className="text-xs font-medium text-gray-300/90 tracking-wide">
                          AI Generated
                        </span>
                      </div>
                    </div>
                  )}
                  <MessageContent message={message} />
                  {/* Action buttons for AI messages */}
                  {message.sender === "ai" && message.finalAnswer && (
                    <MessageActions message={message} />
                  )}
                </div>
              </motion.div>
            ))}
            {/* Show loading indicator when:
                1. isTyping - user just sent a message
                2. isLiveRequest && currentStreamingMessageId && !isTyping - reconnection to active stream */}
            {(isTyping || (isLiveRequest && currentStreamingMessageId && !isTyping)) && 
              (isChatOnlyMode ? ChatOnlyLoader : TypingIndicator)}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
        <div className="p-4 border-t border-gray-800 flex-shrink-0">
          {/* Status banners - priority order: deleted > sharing disabled > invalid > validating */}
          {!blueprintExists && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.deleted} />
          )}
          {blueprintExists && isSharingDisabled && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.sharingDisabled} />
          )}
          {blueprintExists && !isSharingDisabled && !blueprintValid && !isValidatingBlueprint && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.validationFailed} />
          )}
          {blueprintExists && !isSharingDisabled && isValidatingBlueprint && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.validating} />
          )}
          
          {/* Input area */}
          <div className="flex space-x-2 items-end">
            {/* Textarea container with expand/collapse icon */}
            <div className="relative flex-1">
              <Textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={getInputPlaceholder()}
                className={`bg-background-dark resize-none transition-[height] duration-200 ease-out w-full ${
                  (!blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint) 
                    ? 'opacity-50 cursor-not-allowed' 
                    : ''
                } ${(isAtMaxHeight || isExpanded) ? 'pr-10' : ''}`}
                style={{ height: `${TEXTAREA_MIN_HEIGHT}px` }}
                rows={1}
                disabled={!blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint}
              />
              {/* Expand/Collapse icon - shows when textarea is at max height or expanded */}
              <AnimatePresence>
                {(isAtMaxHeight || isExpanded) && (
                  <motion.button
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.15 }}
                    onClick={toggleExpandedHeight}
                    className={`absolute top-2 right-2 p-1.5 rounded-md transition-colors border ${
                      isExpanded 
                        ? 'bg-primary/20 text-primary border-primary/50 hover:bg-primary/30' 
                        : 'bg-background-surface/90 hover:bg-primary/20 text-gray-400 hover:text-primary border-gray-700 hover:border-primary/50'
                    }`}
                    title={isExpanded ? "Collapse input area" : "Expand input area"}
                    type="button"
                  >
                    {isExpanded ? (
                      <Minimize2 className="h-3.5 w-3.5" />
                    ) : (
                      <Maximize2 className="h-3.5 w-3.5" />
                    )}
                  </motion.button>
                )}
              </AnimatePresence>
            </div>
            <UmamiTrack 
              event={UmamiEvents.AGENT_CHAT_SEND_MESSAGE_BUTTON}
            >
              <Button
                onClick={() => handleSendMessage()}
                disabled={inputMessage.trim() === "" || isTyping || !blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint}
                className="bg-primary hover:bg-[#7525c9] mb-0"
              >
                <Send className="h-4 w-4" />
              </Button>
            </UmamiTrack>
          </div>
          <div className="flex items-start gap-2 mt-2 px-1">
            <Info className="h-3.5 w-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-gray-500">
              AI agent responses may be inaccurate or incomplete. Always review AI generated content prior to use.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}