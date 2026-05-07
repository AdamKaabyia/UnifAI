import axios from "@/http/axiosAgentConfig";

export const sendTypingSignal = async (
  sessionId: string,
  userId: string,
  isTyping: boolean,
) => {
  return axios.post("/collaboration/session.typing", {
    sessionId,
    userId,
    isTyping,
  });
};
