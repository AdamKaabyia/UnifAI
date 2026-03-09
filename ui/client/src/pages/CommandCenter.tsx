import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FaTachometerAlt,
  FaProjectDiagram,
  FaUsers,
  FaTrophy,
} from "react-icons/fa";
import {
  Users,
  Share2,
  Zap,
  TrendingUp,
  Activity,
  GitFork,
  Eye,
  Lock,
  Search,
  MessageSquare,
  Send,
  Link2,
  ChevronRight,
  ChevronDown,
  Radio,
  Crown,
  Medal,
  Award,
  CircleDot,
} from "lucide-react";

import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import GlassPanel from "@/components/ui/GlassPanel";
import { StatCard } from "@/components/ui/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";

// ─── Mock Data ───────────────────────────────────────────────────────────────

const MOCK_TEAM_MEMBERS = [
  { id: "1", name: "Sarah K.", initials: "SK", color: "from-blue-500 to-blue-600" },
  { id: "2", name: "David M.", initials: "DM", color: "from-emerald-500 to-emerald-600" },
  { id: "3", name: "Lisa R.", initials: "LR", color: "from-pink-500 to-pink-600" },
  { id: "4", name: "James C.", initials: "JC", color: "from-orange-500 to-orange-600" },
  { id: "5", name: "Alex K.", initials: "AK", color: "from-violet-500 to-violet-600" },
  { id: "6", name: "Maria T.", initials: "MT", color: "from-cyan-500 to-cyan-600" },
];

const MOCK_TEAMS = [
  { id: "team-1", name: "Platform Engineering", members: [MOCK_TEAM_MEMBERS[0], MOCK_TEAM_MEMBERS[1], MOCK_TEAM_MEMBERS[2], MOCK_TEAM_MEMBERS[3], MOCK_TEAM_MEMBERS[4], MOCK_TEAM_MEMBERS[5]] },
  { id: "team-2", name: "SRE", members: [MOCK_TEAM_MEMBERS[0], MOCK_TEAM_MEMBERS[4], MOCK_TEAM_MEMBERS[5]] },
];

const MOCK_ACTIVITY = [
  { user: MOCK_TEAM_MEMBERS[0], action: "joined War Room", target: "Incident Triage", time: "Just now" },
  { user: MOCK_TEAM_MEMBERS[1], action: "published", target: "OpenShift Retrieval Tool", suffix: "to Team Registry", time: "2m ago" },
  { user: MOCK_TEAM_MEMBERS[2], action: "forked", target: "SRE Auto-Medic", time: "8m ago" },
  { user: MOCK_TEAM_MEMBERS[3], action: "started", target: "Compliance Audit", time: "15m ago" },
  { user: MOCK_TEAM_MEMBERS[4], action: "deployed", target: "Jira Story Generator", suffix: "v2.1", time: "32m ago" },
  { user: MOCK_TEAM_MEMBERS[5], action: "shared", target: "RHEL Diagnostics MCP", suffix: "with team", time: "1h ago" },
  { user: MOCK_TEAM_MEMBERS[0], action: "ran", target: "SRE Auto-Medic", suffix: "(42nd run!)", time: "1h ago" },
  { user: MOCK_TEAM_MEMBERS[1], action: "added prompt", target: "Jira Summarizer", suffix: "to Team Registry", time: "2h ago" },
];

const MOCK_LEADERBOARD = [
  { name: "SRE Auto-Medic", runs: 42, users: 6, forks: 3, saved: "~18 hrs", pct: 100 },
  { name: "Compliance Auditor", runs: 28, users: 4, forks: 1, saved: "~8 hrs", pct: 67 },
  { name: "Jira Story Generator", runs: 15, users: 5, forks: 2, saved: "~3 hrs", pct: 36 },
  { name: "OpenShift Retrieval Agent", runs: 8, users: 3, forks: 0, saved: "~2 hrs", pct: 19 },
];

type AssetKind = "workflow" | "tool" | "mcp" | "template";

interface MockAsset {
  name: string;
  kind: AssetKind;
  desc: string;
  author: (typeof MOCK_TEAM_MEMBERS)[number];
  runs: number;
  users: number;
  forks: number;
  visibility: "team" | "private";
  forkedFrom?: string;
}

const MOCK_ASSETS: MockAsset[] = [
  { name: "SRE Auto-Medic", kind: "workflow", desc: "Autonomous incident triage: pulls logs, checks metrics, suggests runbooks, and can execute remediation steps.", author: MOCK_TEAM_MEMBERS[0], runs: 42, users: 6, forks: 3, visibility: "team" },
  { name: "Compliance Auditor", kind: "workflow", desc: "Scans infrastructure configs against CIS benchmarks, generates compliance reports and remediation tickets.", author: MOCK_TEAM_MEMBERS[3], runs: 28, users: 4, forks: 1, visibility: "team" },
  { name: "RHEL Diagnostics", kind: "mcp", desc: "MCP server for Red Hat Enterprise Linux diagnostics. Exposes sosreport analysis, systemd inspection, and kernel log parsing.", author: MOCK_TEAM_MEMBERS[5], runs: 19, users: 5, forks: 0, visibility: "team" },
  { name: "OpenShift Retrieval Agent", kind: "tool", desc: "RAG-powered retrieval over OpenShift documentation and internal runbooks. Supports contextual Q&A.", author: MOCK_TEAM_MEMBERS[1], runs: 8, users: 3, forks: 0, visibility: "team" },
  { name: "Jira Story Generator", kind: "template", desc: "Generates well-structured Jira stories from a natural language description. Includes acceptance criteria and subtasks.", author: MOCK_TEAM_MEMBERS[2], runs: 15, users: 5, forks: 2, visibility: "team", forkedFrom: "Alex K.'s Story Builder" },
  { name: "Log Anomaly Detector", kind: "workflow", desc: "Experimental workflow for detecting anomalous patterns in application logs using embedding similarity.", author: MOCK_TEAM_MEMBERS[4], runs: 2, users: 1, forks: 0, visibility: "private" },
];

interface MockSession {
  name: string;
  blueprint: string;
  status: "running" | "idle";
  duration: string;
  participants: (typeof MOCK_TEAM_MEMBERS)[number][];
}

const MOCK_SESSIONS: MockSession[] = [
  { name: "Incident Triage — PROD-4521", blueprint: "SRE Auto-Medic", status: "running", duration: "12m", participants: [MOCK_TEAM_MEMBERS[0], MOCK_TEAM_MEMBERS[1], MOCK_TEAM_MEMBERS[2]] },
  { name: "Compliance Audit — Q1 Review", blueprint: "Compliance Auditor", status: "running", duration: "4m", participants: [MOCK_TEAM_MEMBERS[3]] },
  { name: "Perf Analysis — api-gw", blueprint: "SRE Auto-Medic", status: "idle", duration: "2h ago", participants: [MOCK_TEAM_MEMBERS[4]] },
];

interface ChatMsg {
  sender: (typeof MOCK_TEAM_MEMBERS)[number] | "ai";
  agentName?: string;
  time: string;
  text: string;
}

const MOCK_CHAT: ChatMsg[] = [
  { sender: MOCK_TEAM_MEMBERS[0], time: "14:23", text: "Hey team, PROD-4521 is showing 502s on the API gateway. I've started the Auto-Medic. Let's triage together." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:23", text: "Starting incident triage for **PROD-4521**.\n\n**Step 1: Log Analysis**\nPulling logs from `api-gateway-prod` cluster...\nFound **847 error entries** in the last 15 minutes.\nTop error: `upstream connect timeout (110)` — 92% of errors.\n\n**Step 2: Metric Check**\nCPU: 34% (normal) · Memory: 71% (elevated) · Network: Packet loss 2.3%\n\nPreliminary assessment: upstream service `payment-svc` is unresponsive. Checking pods..." },
  { sender: MOCK_TEAM_MEMBERS[1], time: "14:25", text: "Can you also check if there was a recent deployment to payment-svc? I think someone pushed a change this morning." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:25", text: "Checking deployment history for `payment-svc`...\n\n**Last deployment:** today 09:14 UTC by deploy-bot\nImage: `payment-svc:v3.8.2` → `payment-svc:v3.9.0`\nCommit: feat: add retry logic for bank API\n\n⚠ The timing correlates. Errors began at ~09:18 UTC, 4 minutes after the deploy. Recommend rollback to `v3.8.2`." },
  { sender: MOCK_TEAM_MEMBERS[2], time: "14:26", text: "Hold on — don't rollback yet. Can you check if the retry logic has a backoff? It might be hammering the bank API and causing cascading failures." },
  { sender: "ai", agentName: "SRE Auto-Medic", time: "14:27", text: "Good catch. Analyzing commit `v3.9.0` diff...\n\n**Finding:** The retry logic uses a fixed 100ms interval with **no exponential backoff** and **no max retry limit**. Under bank API latency, this creates a retry storm.\n\n**Recommendation:**\n1. Immediate: Scale down `payment-svc` replicas to 1 to reduce blast radius\n2. Short-term: Rollback to `v3.8.2`\n3. Fix: Add exponential backoff (base=500ms, max=30s, limit=5 retries)\n\nShall I create a Jira ticket for the fix?" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function Avatar({ member, size = "sm" }: { member: (typeof MOCK_TEAM_MEMBERS)[number]; size?: "xs" | "sm" | "md" }) {
  const sizeClasses = { xs: "w-5 h-5 text-[9px]", sm: "w-7 h-7 text-[10px]", md: "w-8 h-8 text-xs" };
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-gradient-to-br ${member.color} flex items-center justify-center font-bold text-white flex-shrink-0`}>
      {member.initials}
    </div>
  );
}

const ASSET_BADGE_STYLES: Record<AssetKind, string> = {
  workflow: "bg-violet-500/15 text-violet-400 border-violet-500/20",
  tool: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  mcp: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  template: "bg-blue-500/15 text-blue-400 border-blue-500/20",
};

const RANK_STYLES = [
  "bg-gradient-to-br from-amber-400 to-amber-600 text-amber-950",
  "bg-gradient-to-br from-slate-300 to-slate-500 text-slate-900",
  "bg-gradient-to-br from-orange-500 to-orange-700 text-white",
];

const RANK_ICONS = [Crown, Medal, Award];

// ─── Component ───────────────────────────────────────────────────────────────

export default function CommandCenter() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeSession, setActiveSession] = useState(0);
  const [registryFilter, setRegistryFilter] = useState<"all" | AssetKind>("all");
  const [registryScope, setRegistryScope] = useState<"team" | "mine">("team");
  const [selectedTeam, setSelectedTeam] = useState(MOCK_TEAMS[0]);
  const [teamSelectorOpen, setTeamSelectorOpen] = useState(false);

  const { user } = useAuth();

  const filteredAssets = MOCK_ASSETS.filter((a) => {
    if (registryScope === "mine" && a.visibility !== "private") return false;
    if (registryScope === "team" && a.visibility !== "team") return false;
    if (registryFilter !== "all" && a.kind !== registryFilter) return false;
    return true;
  });

  const liveSessions = MOCK_SESSIONS.filter((s) => s.status === "running");

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="AI Command Center" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <Tabs defaultValue="dashboard" className="flex-1 flex flex-col overflow-hidden">
          <div className="border-b border-gray-800 bg-background-surface px-6 flex items-center justify-between">
            <TabsList className="bg-transparent h-11 gap-1 p-0">
              <TabsTrigger value="dashboard" className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4">
                <Activity className="w-3.5 h-3.5 mr-2" />Dashboard
              </TabsTrigger>
              <TabsTrigger value="registry" className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4">
                <Share2 className="w-3.5 h-3.5 mr-2" />Team Registry
              </TabsTrigger>
              <TabsTrigger value="warroom" className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4">
                <MessageSquare className="w-3.5 h-3.5 mr-2" />War Room
                {liveSessions.length > 0 && (
                  <Badge className="ml-2 bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px] px-1.5 py-0">
                    {liveSessions.length} live
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            {/* Team Selector */}
            <div className="relative flex-shrink-0">
              <button
                onClick={() => setTeamSelectorOpen(!teamSelectorOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-800 bg-background-card hover:border-gray-700 transition-colors"
              >
                <Users className="w-3.5 h-3.5 text-primary" />
                <span className="font-medium text-white text-xs">{selectedTeam.name}</span>
                <ChevronDown className={`w-3.5 h-3.5 text-gray-500 transition-transform ${teamSelectorOpen ? "rotate-180" : ""}`} />
              </button>

              <AnimatePresence>
                {teamSelectorOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setTeamSelectorOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 top-full mt-2 w-72 bg-[#1a1a2e] border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden"
                    >
                      <div className="p-2 border-b border-gray-800">
                        <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-2 py-1">Your Teams</div>
                        {MOCK_TEAMS.map((team) => (
                          <button
                            key={team.id}
                            onClick={() => { setSelectedTeam(team); setTeamSelectorOpen(false); }}
                            className={`w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-left transition-colors ${selectedTeam.id === team.id ? "bg-primary/10" : "hover:bg-white/[.03]"}`}
                          >
                            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${selectedTeam.id === team.id ? "bg-primary" : "bg-gray-700"}`} />
                            <div className="flex-1 min-w-0">
                              <div className={`text-xs font-semibold truncate ${selectedTeam.id === team.id ? "text-primary" : "text-gray-300"}`}>{team.name}</div>
                              <div className="text-[10px] text-gray-600">{team.members.length} members</div>
                            </div>
                          </button>
                        ))}
                      </div>

                      <div className="p-3">
                        <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                          Members &mdash; {selectedTeam.name}
                        </div>
                        <div className="space-y-1.5">
                          {selectedTeam.members.map((m) => (
                            <div key={m.id} className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                              <Avatar member={m} size="xs" />
                              <span className="text-xs text-gray-300">{m.name}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="px-3 py-2 border-t border-gray-800 bg-gray-900/30">
                        <p className="text-[10px] text-gray-600 italic">Manage teams in the Configuration tab</p>
                      </div>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* ══════════════ DASHBOARD TAB ══════════════ */}
          <TabsContent value="dashboard" className="flex-1 overflow-hidden mt-0">
            <div className="flex h-full">
              <div className="flex-1 overflow-y-auto p-6">

                {/* ROI Banner */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.05 }}>
                  <Card className="mb-6 border-gray-800 bg-gradient-to-r from-primary/10 via-transparent to-pink-500/5 overflow-hidden">
                    <CardContent className="p-5 flex items-center gap-5">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-pink-500 flex items-center justify-center flex-shrink-0">
                        <Zap className="w-6 h-6 text-white" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-bold text-white text-base">Team AI Impact This Week</h3>
                        <p className="text-xs text-gray-400">Across 6 engineers running 58 sessions on 14 shared workflows</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-3xl font-extrabold text-emerald-400 tracking-tight">31 hrs</div>
                        <div className="text-[11px] text-gray-500">estimated saved</div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Stat Cards */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} className="mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  <GlassPanel className="h-full">
                    <StatCard icon={<Share2 className="w-4 h-4" />} title={<span className="flex items-center"><FaProjectDiagram className="text-primary mr-3 h-5 w-5" />Shared Workflows</span>} value={14} subtext="+3 this week" />
                  </GlassPanel>
                  <GlassPanel className="h-full">
                    <StatCard icon={<Users className="w-4 h-4" />} title={<span className="flex items-center"><FaUsers className="text-blue-400 mr-3 h-5 w-5" />Team Members</span>} value={8} subtext="6 active today" iconColor="#60a5fa" iconBgColor="rgba(96,165,250,.15)" />
                  </GlassPanel>
                  <GlassPanel className="h-full">
                    <StatCard icon={<Radio className="w-4 h-4" />} title={<span className="flex items-center"><Zap className="text-emerald-400 mr-3 h-5 w-5" />Active Sessions</span>} value={liveSessions.length} subtext="War Rooms open" iconColor="#34d399" iconBgColor="rgba(52,211,153,.15)" />
                  </GlassPanel>
                  <GlassPanel className="h-full">
                    <StatCard icon={<TrendingUp className="w-4 h-4" />} title={<span className="flex items-center"><FaTrophy className="text-amber-400 mr-3 h-5 w-5" />Total Runs (7d)</span>} value={58} subtext="+22% vs last week" iconColor="#fbbf24" iconBgColor="rgba(251,191,36,.15)" />
                  </GlassPanel>
                </motion.div>

                {/* Live Sessions */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }} className="mb-6">
                  <GlassPanel>
                    <Card className="bg-transparent border-0 shadow-none">
                      <CardHeader className="px-4 py-3 border-b border-gray-800/50">
                        <CardTitle className="text-base flex items-center gap-2">
                          <motion.div className="w-2 h-2 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
                          Live War Room Sessions
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-0">
                        {MOCK_SESSIONS.filter((s) => s.status === "running").map((session, i) => (
                          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/30 last:border-0 hover:bg-white/[.02] transition-colors">
                            <motion.div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-sm text-white truncate">{session.name}</div>
                              <div className="text-xs text-gray-500">{session.blueprint} · running for {session.duration}</div>
                            </div>
                            <div className="flex items-center -space-x-1.5">
                              {session.participants.map((p) => (
                                <div key={p.id} className="ring-2 ring-background-card rounded-full"><Avatar member={p} size="xs" /></div>
                              ))}
                            </div>
                            <Button size="sm" className="bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/20 text-xs h-7 px-3">
                              Join
                            </Button>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  </GlassPanel>
                </motion.div>

                {/* Leaderboard */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
                  <GlassPanel>
                    <Card className="bg-transparent border-0 shadow-none">
                      <CardHeader className="px-4 py-3 border-b border-gray-800/50">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-base flex items-center gap-2">
                            <FaTrophy className="text-amber-400" />
                            Top Workflows — Team Impact
                          </CardTitle>
                          <span className="text-[11px] text-gray-500 bg-gray-800/50 px-2 py-0.5 rounded">Last 7 days</span>
                        </div>
                      </CardHeader>
                      <CardContent className="p-0">
                        {MOCK_LEADERBOARD.map((item, i) => {
                          const RankIcon = RANK_ICONS[i] ?? CircleDot;
                          return (
                            <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/30 last:border-0 hover:bg-white/[.02] transition-colors">
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${i < 3 ? RANK_STYLES[i] : "bg-gray-800 text-gray-500"}`}>
                                {i < 3 ? <RankIcon className="w-3.5 h-3.5" /> : <span className="text-xs font-bold">{i + 1}</span>}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="font-semibold text-sm text-white">{item.name}</div>
                                <div className="text-xs text-gray-500">{item.runs} runs · {item.users} engineers{item.forks > 0 ? ` · ${item.forks} forks` : ""}</div>
                              </div>
                              <div className="w-28 flex-shrink-0">
                                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                  <motion.div className="h-full rounded-full bg-gradient-to-r from-primary to-pink-500" initial={{ width: 0 }} animate={{ width: `${item.pct}%` }} transition={{ duration: 0.8, delay: 0.3 + i * 0.1 }} />
                                </div>
                                <div className="text-[10px] text-gray-600 text-right mt-0.5">{item.runs} runs</div>
                              </div>
                              <div className="text-right flex-shrink-0 w-16">
                                <div className="text-sm font-bold text-emerald-400">{item.saved}</div>
                                <div className="text-[10px] text-gray-600">saved</div>
                              </div>
                            </div>
                          );
                        })}
                      </CardContent>
                    </Card>
                  </GlassPanel>
                </motion.div>
              </div>

              {/* Activity Feed Panel */}
              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.25 }} className="w-[280px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex">
                <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
                  <motion.div className="w-2 h-2 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
                  <span className="font-semibold text-sm text-white">Live Activity</span>
                </div>
                <div className="flex-1 overflow-y-auto">
                  {MOCK_ACTIVITY.map((evt, i) => (
                    <div key={i} className="flex gap-2.5 px-4 py-2.5 border-b border-gray-800/40 hover:bg-white/[.02] transition-colors">
                      <Avatar member={evt.user} size="xs" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs leading-relaxed">
                          <span className="font-semibold text-gray-200">{evt.user.name}</span>{" "}
                          <span className="text-gray-500">{evt.action} </span>
                          <span className="text-primary font-medium">{evt.target}</span>
                          {evt.suffix && <span className="text-gray-500"> {evt.suffix}</span>}
                        </p>
                        <p className="text-[10px] text-gray-600 mt-0.5">{evt.time}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            </div>
          </TabsContent>

          {/* ══════════════ TEAM REGISTRY TAB ══════════════ */}
          <TabsContent value="registry" className="flex-1 overflow-y-auto p-6 mt-0">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

              {/* Filters */}
              <div className="flex items-center gap-3 mb-6 flex-wrap">
                <div className="flex bg-background-card border border-gray-800 rounded-lg p-0.5 gap-0.5">
                  {(["all", "workflow", "tool", "mcp", "template"] as const).map((k) => (
                    <button key={k} onClick={() => setRegistryFilter(k)} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${registryFilter === k ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"}`}>
                      {k === "all" ? "All" : k === "mcp" ? "MCPs" : `${k}s`}
                    </button>
                  ))}
                </div>

                <div className="flex bg-background-card border border-gray-800 rounded-lg p-0.5 gap-0.5">
                  <button onClick={() => setRegistryScope("team")} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors truncate max-w-[160px] ${registryScope === "team" ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"}`}>
                    {selectedTeam.name}
                  </button>
                  <button onClick={() => setRegistryScope("mine")} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${registryScope === "mine" ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"}`}>
                    My Assets
                  </button>
                </div>

                <div className="flex-1 min-w-[200px] relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" />
                  <input type="text" placeholder="Search team assets..." className="w-full bg-background-card border border-gray-800 rounded-lg py-2 pl-9 pr-3 text-xs text-white placeholder:text-gray-600 outline-none focus:border-primary/50 transition-colors" />
                </div>
              </div>

              {/* Asset Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                <AnimatePresence mode="popLayout">
                  {filteredAssets.map((asset) => (
                    <motion.div key={asset.name} layout initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.2 }}>
                      <Card className={`border-gray-800 hover:border-gray-700 transition-all cursor-pointer group ${asset.visibility === "private" ? "opacity-60" : ""}`}>
                        <CardContent className="p-5">
                          <div className="flex items-start justify-between mb-3">
                            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${ASSET_BADGE_STYLES[asset.kind]}`}>
                              {asset.kind}
                            </span>
                            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                              {asset.visibility === "team" ? (
                                <><Eye className="w-3 h-3" />{selectedTeam.name}</>
                              ) : (
                                <><Lock className="w-3 h-3" />Private</>
                              )}
                            </div>
                          </div>
                          <h4 className="font-bold text-white text-sm mb-1 group-hover:text-primary transition-colors">{asset.name}</h4>
                          <p className="text-xs text-gray-500 leading-relaxed mb-3 line-clamp-2">{asset.desc}</p>
                          {asset.forkedFrom && (
                            <div className="flex items-center gap-1 text-[10px] text-gray-600 bg-gray-800/50 rounded px-2 py-1 mb-3 w-fit">
                              <GitFork className="w-3 h-3" />
                              Forked from: {asset.forkedFrom}
                            </div>
                          )}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Avatar member={asset.author} size="xs" />
                              <span className="text-[11px] text-gray-500">{asset.author.name}</span>
                            </div>
                            <div className="flex gap-3 text-[11px] text-gray-600">
                              <span>{asset.runs} runs</span>
                              <span>{asset.users} users</span>
                              {asset.forks > 0 && <span>{asset.forks} forks</span>}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>

              {filteredAssets.length === 0 && (
                <div className="text-center py-20 text-gray-600">
                  <Share2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">No assets match the current filters.</p>
                </div>
              )}
            </motion.div>
          </TabsContent>

          {/* ══════════════ WAR ROOM TAB ══════════════ */}
          <TabsContent value="warroom" className="flex-1 overflow-hidden mt-0">
            <div className="flex h-full">

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
                          <div key={p.id} className="ring-2 ring-background-card rounded-full"><Avatar member={p} size="xs" /></div>
                        ))}
                        <span className="text-[10px] text-gray-600 ml-2">{session.participants.length} in room</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Chat Area */}
              <div className="flex-1 flex flex-col min-w-0">
                {/* Chat Header */}
                <div className="px-5 py-3 border-b border-gray-800 bg-background-surface flex items-center gap-3">
                  <motion.div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                  <span className="font-bold text-sm text-white flex-1">{MOCK_SESSIONS[activeSession].name}</span>
                  <div className="flex items-center -space-x-1.5">
                    {MOCK_SESSIONS[activeSession].participants.map((p) => (
                      <div key={p.id} className="ring-2 ring-background-surface rounded-full"><Avatar member={p} size="xs" /></div>
                    ))}
                    <span className="text-xs text-gray-500 ml-2">{MOCK_SESSIONS[activeSession].participants.length} online</span>
                  </div>
                  <Button variant="outline" size="sm" className="text-xs h-7 border-gray-700">
                    <Link2 className="w-3 h-3 mr-1" />Invite
                  </Button>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                  {MOCK_CHAT.map((msg, i) => {
                    const isAI = msg.sender === "ai";
                    const member = isAI ? null : msg.sender;
                    return (
                      <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.05 }} className="flex gap-3 max-w-[88%]">
                        {isAI ? (
                          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-pink-500 flex items-center justify-center flex-shrink-0 text-[9px] font-bold text-white">AI</div>
                        ) : (
                          <Avatar member={member!} size="sm" />
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

                {/* Queue Indicator */}
                <div className="px-5 py-1.5 bg-orange-500/5 border-t border-orange-500/10 flex items-center gap-2 text-[11px] text-orange-400 font-medium">
                  <Activity className="w-3 h-3" />
                  1 prompt queued (Sarah K.) — executing current response
                </div>

                {/* Typing Indicator */}
                <div className="px-5 py-1 text-[11px] text-gray-600 italic">
                  Sarah K. is typing...
                </div>

                {/* Input */}
                <div className="px-5 py-3 border-t border-gray-800 bg-background-surface flex gap-3 items-center">
                  <input type="text" placeholder="Message the War Room... (all participants will see)" className="flex-1 bg-background-card border border-gray-800 rounded-lg py-2.5 px-4 text-xs text-white placeholder:text-gray-600 outline-none focus:border-primary/50 transition-colors" />
                  <Button size="sm" className="h-9 px-4">
                    <Send className="w-3.5 h-3.5 mr-1.5" />Send
                  </Button>
                </div>
              </div>

              {/* Right Panel: Participants + Graph + Info */}
              <div className="w-[260px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex">
                {/* Participants */}
                <div className="px-4 py-3 border-b border-gray-800">
                  <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Participants ({MOCK_SESSIONS[activeSession].participants.length})
                  </div>
                  {MOCK_SESSIONS[activeSession].participants.map((p) => (
                    <div key={p.id} className="flex items-center gap-2 py-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                      <Avatar member={p} size="xs" />
                      <span className="text-xs text-gray-300 flex-1">{p.name}</span>
                      <span className="text-[10px] text-gray-600">Editor</span>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="w-full mt-3 text-[11px] h-7 border-gray-700 text-gray-500 hover:text-gray-300">
                    + Invite Team Member
                  </Button>
                </div>

                {/* Mini Graph */}
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

                {/* Session Info */}
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
          </TabsContent>
        </Tabs>

        <StatusBar />
      </div>
    </div>
  );
}
