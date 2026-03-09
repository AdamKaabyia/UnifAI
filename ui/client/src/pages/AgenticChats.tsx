
import React, { useState } from "react";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  Activity, Link2, Send,
} from "lucide-react";
import { useView } from "@/contexts/ViewContext";

import ExecutionTab from "@/components/agentic-ai/ExecutionTab";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";

// ─── War Room Mock Data ──────────────────────────────────────────────────────

const WARROOM_MOCK_MEMBERS = [
  { id: "1", name: "Sarah K.", initials: "SK", color: "from-blue-500 to-blue-600" },
  { id: "2", name: "David M.", initials: "DM", color: "from-emerald-500 to-emerald-600" },
  { id: "3", name: "Lisa R.", initials: "LR", color: "from-pink-500 to-pink-600" },
  { id: "4", name: "James C.", initials: "JC", color: "from-orange-500 to-orange-600" },
  { id: "5", name: "Alex K.", initials: "AK", color: "from-violet-500 to-violet-600" },
  { id: "6", name: "Maria T.", initials: "MT", color: "from-cyan-500 to-cyan-600" },
];

interface MockSession {
  name: string;
  blueprint: string;
  status: "running" | "idle";
  duration: string;
  participants: (typeof WARROOM_MOCK_MEMBERS)[number][];
}

const MOCK_SESSIONS: MockSession[] = [
  { name: "Incident Triage — PROD-4521", blueprint: "SRE Auto-Medic", status: "running", duration: "12m", participants: [WARROOM_MOCK_MEMBERS[0], WARROOM_MOCK_MEMBERS[1], WARROOM_MOCK_MEMBERS[2]] },
  { name: "Compliance Audit — Q1 Review", blueprint: "Compliance Auditor", status: "running", duration: "4m", participants: [WARROOM_MOCK_MEMBERS[3]] },
  { name: "Perf Analysis — api-gw", blueprint: "SRE Auto-Medic", status: "idle", duration: "2h ago", participants: [WARROOM_MOCK_MEMBERS[4]] },
];

interface ChatMsg {
  sender: (typeof WARROOM_MOCK_MEMBERS)[number] | "ai";
  agentName?: string;
  time: string;
  text: string;
}

const MOCK_CHAT: ChatMsg[] = [
  { sender: WARROOM_MOCK_MEMBERS[0], time: "14:23", text: "Hey team, PROD-4521 is showing 502s on the API gateway. I've started the Auto-Medic. Let's triage together." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:23", text: "Starting incident triage for **PROD-4521**.\n\n**Step 1: Log Analysis**\nPulling logs from `api-gateway-prod` cluster...\nFound **847 error entries** in the last 15 minutes.\nTop error: `upstream connect timeout (110)` — 92% of errors.\n\n**Step 2: Metric Check**\nCPU: 34% (normal) · Memory: 71% (elevated) · Network: Packet loss 2.3%\n\nPreliminary assessment: upstream service `payment-svc` is unresponsive. Checking pods..." },
  { sender: WARROOM_MOCK_MEMBERS[1], time: "14:25", text: "Can you also check if there was a recent deployment to payment-svc? I think someone pushed a change this morning." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:25", text: "Checking deployment history for `payment-svc`...\n\n**Last deployment:** today 09:14 UTC by deploy-bot\nImage: `payment-svc:v3.8.2` → `payment-svc:v3.9.0`\nCommit: feat: add retry logic for bank API\n\n⚠ The timing correlates. Errors began at ~09:18 UTC, 4 minutes after the deploy. Recommend rollback to `v3.8.2`." },
  { sender: WARROOM_MOCK_MEMBERS[2], time: "14:26", text: "Hold on — don't rollback yet. Can you check if the retry logic has a backoff? It might be hammering the bank API and causing cascading failures." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:27", text: "Good catch. Analyzing commit `v3.9.0` diff...\n\n**Finding:** The retry logic uses a fixed 100ms interval with **no exponential backoff** and **no max retry limit**. Under bank API latency, this creates a retry storm.\n\n**Recommendation:**\n1. Immediate: Scale down `payment-svc` replicas to 1 to reduce blast radius\n2. Short-term: Rollback to `v3.8.2`\n3. Fix: Add exponential backoff (base=500ms, max=30s, limit=5 retries)\n\nShall I create a Jira ticket for the fix?" },
];

function WarRoomAvatar({ member, size = "sm" }: { member: (typeof WARROOM_MOCK_MEMBERS)[number]; size?: "xs" | "sm" }) {
  const sizeClasses = { xs: "w-5 h-5 text-[9px]", sm: "w-7 h-7 text-[10px]" };
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-gradient-to-br ${member.color} flex items-center justify-center font-bold text-white flex-shrink-0`}>
      {member.initials}
    </div>
  );
}

export default function AgenticChats() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeSession, setActiveSession] = useState(0);
  const { viewMode } = useView();
  const isTeam = viewMode === "team";

  return (
    <>
      <Header
        title={isTeam ? "War Room" : "Agentic Chats"}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

        {isTeam ? (
          /* ═══════ WAR ROOM VIEW ═══════ */
          <div className="flex flex-1 overflow-hidden">
            {/* Session List */}
            <div className="w-[260px] border-r border-gray-800 bg-background-card flex flex-col flex-shrink-0">
              <div className="px-4 py-3 border-b border-gray-800 font-semibold text-sm text-white">Active Sessions</div>
              <div className="flex-1 overflow-y-auto">
                {MOCK_SESSIONS.map((session, i) => (
                  <div key={i} onClick={() => setActiveSession(i)} className={`px-4 py-3 border-b border-gray-800/50 cursor-pointer transition-colors ${activeSession === i ? "bg-primary/10" : "hover:bg-white/[.02]"}`}>
                    <div className="font-semibold text-xs text-white truncate">{session.name}</div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <motion.div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${session.status === "running" ? "bg-emerald-400" : "bg-orange-400"}`} animate={session.status === "running" ? { opacity: [1, 0.4, 1] } : {}} transition={{ duration: 1.5, repeat: Infinity }} />
                      <span className={`text-[11px] font-medium ${session.status === "running" ? "text-emerald-400" : "text-orange-400"}`}>
                        {session.status === "running" ? "Running" : "Idle"}
                      </span>
                      <span className="text-[11px] text-gray-600">{session.duration}</span>
                    </div>
                    <div className="flex items-center mt-2 -space-x-1">
                      {session.participants.map((p) => (
                        <div key={p.id} className="ring-2 ring-background-card rounded-full"><WarRoomAvatar member={p} size="xs" /></div>
                      ))}
                      <span className="text-[10px] text-gray-600 ml-2">{session.participants.length} in room</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col min-w-0">
              <div className="px-5 py-3 border-b border-gray-800 bg-background-surface flex items-center gap-3">
                <motion.div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                <span className="font-bold text-sm text-white flex-1">{MOCK_SESSIONS[activeSession].name}</span>
                <div className="flex items-center -space-x-1.5">
                  {MOCK_SESSIONS[activeSession].participants.map((p) => (
                    <div key={p.id} className="ring-2 ring-background-surface rounded-full"><WarRoomAvatar member={p} size="xs" /></div>
                  ))}
                  <span className="text-xs text-gray-500 ml-2">{MOCK_SESSIONS[activeSession].participants.length} online</span>
                </div>
                <Button variant="outline" size="sm" className="text-xs h-7 border-gray-700">
                  <Link2 className="w-3 h-3 mr-1" />Invite
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {MOCK_CHAT.map((msg, i) => {
                  const isAI = msg.sender === "ai";
                  const member = isAI ? null : msg.sender;
                  return (
                    <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.05 }} className="flex gap-3 max-w-[88%]">
                      {isAI ? (
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-pink-500 flex items-center justify-center flex-shrink-0 text-[9px] font-bold text-white">AI</div>
                      ) : (
                        <WarRoomAvatar member={member!} size="sm" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-bold ${isAI ? "text-primary" : "text-gray-300"}`}>
                            {isAI ? msg.agentName : member!.name}
                          </span>
                          <span className="text-[10px] text-gray-600">{msg.time}</span>
                        </div>
                        <div className={`text-[13px] leading-relaxed rounded-lg px-3.5 py-2.5 border ${isAI ? "bg-primary/5 border-primary/10 text-gray-300" : "bg-background-card border-gray-800 text-gray-400"}`}>
                          {msg.text.split("\n").map((line, j) => (
                            <span key={j}>
                              {line.split(/(\*\*.*?\*\*|`[^`]+`)/).map((seg, k) => {
                                if (seg.startsWith("**") && seg.endsWith("**"))
                                  return <strong key={k} className="text-white font-semibold">{seg.slice(2, -2)}</strong>;
                                if (seg.startsWith("`") && seg.endsWith("`"))
                                  return <code key={k} className="bg-gray-800/80 text-amber-300/80 px-1 py-0.5 rounded text-[11px] font-mono">{seg.slice(1, -1)}</code>;
                                if (seg.startsWith("⚠"))
                                  return <span key={k} className="text-orange-400 font-semibold">{seg}</span>;
                                return <span key={k}>{seg}</span>;
                              })}
                              {j < msg.text.split("\n").length - 1 && <br />}
                            </span>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              <div className="px-5 py-1.5 bg-orange-500/5 border-t border-orange-500/10 flex items-center gap-2 text-[11px] text-orange-400 font-medium">
                <Activity className="w-3 h-3" />
                1 prompt queued (Sarah K.) — executing current response
              </div>
              <div className="px-5 py-1 text-[11px] text-gray-600 italic">
                Sarah K. is typing...
              </div>
              <div className="px-5 py-3 border-t border-gray-800 bg-background-surface flex gap-3 items-center">
                <input type="text" placeholder="Message the War Room... (all participants will see)" className="flex-1 bg-background-card border border-gray-800 rounded-lg py-2.5 px-4 text-xs text-white placeholder:text-gray-600 outline-none focus:border-primary/50 transition-colors" />
                <Button size="sm" className="h-9 px-4">
                  <Send className="w-3.5 h-3.5 mr-1.5" />Send
                </Button>
              </div>
            </div>

            {/* Right Panel */}
            <div className="w-[260px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex">
              <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Participants ({MOCK_SESSIONS[activeSession].participants.length})
                </div>
                {MOCK_SESSIONS[activeSession].participants.map((p) => (
                  <div key={p.id} className="flex items-center gap-2 py-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                    <WarRoomAvatar member={p} size="xs" />
                    <span className="text-xs text-gray-300 flex-1">{p.name}</span>
                    <span className="text-[10px] text-gray-600">Editor</span>
                  </div>
                ))}
                <Button variant="outline" size="sm" className="w-full mt-3 text-[11px] h-7 border-gray-700 text-gray-500 hover:text-gray-300">
                  + Invite Team Member
                </Button>
              </div>

              <div className="px-4 py-3 border-b border-gray-800 flex-1">
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">Workflow Graph</div>
                <div className="bg-background-dark border border-gray-800 rounded-lg h-40 relative overflow-hidden flex items-center justify-center">
                  <div className="absolute left-3 top-4 bg-background-card border border-primary/30 rounded-md px-2 py-1 text-[9px] font-semibold text-gray-400 shadow-[0_0_8px_rgba(var(--primary),0.15)]">
                    <span className="text-emerald-400 mr-1">✓</span>Log Analysis
                  </div>
                  <div className="absolute right-3 top-4 bg-background-card border border-primary/30 rounded-md px-2 py-1 text-[9px] font-semibold text-gray-400">
                    <span className="text-emerald-400 mr-1">✓</span>Metric Check
                  </div>
                  <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background-card border-2 border-emerald-400 rounded-md px-2 py-1 text-[9px] font-semibold text-white shadow-[0_0_12px_rgba(16,185,129,0.2)]">
                    <motion.span className="text-emerald-400 mr-1" animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1, repeat: Infinity }}>▶</motion.span>
                    Deploy History
                  </div>
                  <div className="absolute left-4 bottom-4 bg-background-card border border-gray-700 rounded-md px-2 py-1 text-[9px] font-semibold text-gray-500">
                    Code Analysis
                  </div>
                  <div className="absolute right-4 bottom-4 bg-background-card border border-gray-700 rounded-md px-2 py-1 text-[9px] font-semibold text-gray-500">
                    Recommend
                  </div>
                </div>
              </div>

              <div className="px-4 py-3">
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">Session Info</div>
                <dl className="text-xs text-gray-500 space-y-1">
                  <div className="flex justify-between"><dt className="font-medium text-gray-400">Blueprint</dt><dd>{MOCK_SESSIONS[activeSession].blueprint}</dd></div>
                  <div className="flex justify-between"><dt className="font-medium text-gray-400">Started</dt><dd>14:23 UTC</dd></div>
                  <div className="flex justify-between"><dt className="font-medium text-gray-400">Status</dt><dd className="text-emerald-400 font-semibold">Running</dd></div>
                  <div className="flex justify-between"><dt className="font-medium text-gray-400">Messages</dt><dd>6</dd></div>
                  <div className="flex justify-between"><dt className="font-medium text-gray-400">Queued</dt><dd className="text-orange-400">1</dd></div>
                </dl>
              </div>
            </div>
          </div>
        ) : (
          /* ═══════ PRIVATE CHATS VIEW ═══════ */
          <>
            <main className="flex-1 overflow-y-auto bg-background-dark">
              <div className="p-6">
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <StreamingDataProvider>
                    <ExecutionTab runId={null} />
                  </StreamingDataProvider>
                </motion.div>
              </div>
            </main>
            <StatusBar />
          </>
        )}
    </>
  );
}