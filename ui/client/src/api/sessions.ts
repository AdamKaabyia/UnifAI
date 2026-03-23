import axios from '@/http/axiosAgentConfig';

export interface CreateSessionParams {
  blueprintId: string;
  userId: string;
}

export async function createSession(params: CreateSessionParams) {
  const response = await axios.post('/sessions/user.session.create', params);
  return response.data;
}

/**
 * Submit Session Request Parameters
 * Used for fire-and-forget background execution
 */
export interface SubmitSessionParams {
  sessionId: string;
  inputs: Record<string, any>;
  scope?: 'public' | 'private';
  loggedInUser?: string;
}

/**
 * Submit Session Response
 * Returned immediately with HTTP 202 - session runs in background
 */
export interface SubmitSessionResponse {
  sessionId: string;
  workflowId?: string;
}

/**
 * Submit a session for background execution.
 * Returns immediately with HTTP 202 — the session runs asynchronously.
 * 
 * After calling this, use subscribeToSessionStream() to receive real-time events.
 * 
 * @param params - Session submission parameters
 * @returns Session ID and workflow ID (if using Temporal)
 * @throws Error if submission fails (400, 500)
 */
export async function submitSession(params: SubmitSessionParams): Promise<SubmitSessionResponse> {
  const response = await axios.post('/sessions/user.session.submit', params);
  return response.data;
}

/**
 * Redis Stream Status Response
 */
export interface StreamStatusResponse {
  session_id: string;
  status: 'running' | 'completed' | 'failed' | 'unknown';
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  error: string | null;
  event_count: number;
  last_event_id: string | null;
  is_active: boolean;
}

/**
 * Check the streaming status of a session via Redis.
 * Returns null if Redis is unavailable, session not found, or timeout.
 */
export async function getSessionStreamStatus(sessionId: string): Promise<StreamStatusResponse | null> {
  try {
    const response = await axios.get(`/sessions/session.stream.status?sessionId=${sessionId}`, {
      timeout: 5000, // 5 second timeout to prevent hanging
    });
    return response.data;
  } catch (err: any) {
    // Gracefully handle unavailable Redis, not found, or timeout
    if (err.response?.status === 503 || err.response?.status === 404 || err.code === 'ECONNABORTED') {
      return null;
    }
    console.error('Error fetching stream status:', err);
    return null;
  }
}

/**
 * Subscribe to a session's Redis stream.
 * Returns a Response object for streaming, or null if unavailable.
 * 
 * The stream replays all events from the beginning, then blocks and streams
 * live events as they arrive. Connection stays open until session completes.
 * 
 * @param sessionId - The session to subscribe to
 */
export async function subscribeToSessionStream(sessionId: string): Promise<Response | null> {
  try {
    const response = await fetch(
      `/api2/sessions/session.subscribe?sessionId=${sessionId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/x-ndjson',
        },
      }
    );
    
    if (!response.ok) {
      console.warn(`Stream subscription failed: ${response.status}`);
      return null;
    }
    
    return response;
  } catch (err) {
    console.error('Error subscribing to stream:', err);
    return null;
  }
}