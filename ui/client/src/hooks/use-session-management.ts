/**
 * Custom hook for session management operations
 */

import { useState, useCallback } from 'react';
import axios from '@/http/axiosAgentConfig';
import { ChatSession, SessionStateData, ChatMessage } from '@/types/session';
import { getPreviewText } from '@/utils/sessionHelpers';

/**
 * Fetch session chat data (messages and output) for a specific session
 */
export const fetchSessionState = async (sessionId: string): Promise<SessionStateData | null> => {
  try {
    const response = await axios.get(`/sessions/session.chat.get?sessionId=${sessionId}`);
    return response.data;
  } catch (err) {
    console.error('Error fetching session state:', err);
    return null;
  }
};

/**
 * Fetch only session messages for a specific session (lightweight)
 */
export const fetchSessionMessages = async (sessionId: string): Promise<ChatMessage[] | null> => {
  try {
    const response = await axios.get(`/sessions/session.chat.get?sessionId=${sessionId}`);
    return response.data?.messages ?? null;
  } catch (err) {
    console.error('Error fetching session messages:', err);
    return null;
  }
};

/**
 * Hook for managing session selection and message loading
 */
export const useSessionManagement = () => {
  const [currentMessages, setCurrentMessages] = useState<ChatMessage[]>([]);

  const loadSessionMessages = useCallback(
    async (session: ChatSession): Promise<ChatSession | null> => {
      // Always fetch fresh messages from the backend to ensure we have the latest data
      const messages = await fetchSessionMessages(session.id);
      if (messages && messages.length > 0) {
        setCurrentMessages(messages);

        // Update the session with loaded messages and preview
        const updatedSession: ChatSession = {
          ...session,
          messages: messages,
          preview: getPreviewText(messages),
        };

        return updatedSession;
      }

      // If no messages from backend, fall back to session's existing messages
      if (session.messages && session.messages.length > 0) {
        setCurrentMessages(session.messages);
        return session;
      }

      return null;
    },
    []
  );

  const clearMessages = useCallback(() => {
    setCurrentMessages([]);
  }, []);

  return {
    currentMessages,
    loadSessionMessages,
    clearMessages,
    setCurrentMessages,
  };
};

