import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
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
  Radio,
  Crown,
  Medal,
  Award,
  CircleDot,
  Rocket,
} from "lucide-react";

import Header from "@/components/layout/Header";
import GlassPanel from "@/components/ui/GlassPanel";
import { StatCard } from "@/components/ui/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import CollaborationHubView, { buildMemberDisplay, MemberDisplay } from "@/components/agentic-ai/CollaborationHubView";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";

// ─── Demo Data (Phase 2 will replace with real API data) ─────────────────────

const DEMO_ACTIVITY = [
  { action: "joined Collaboration Hub", target: "Incident Triage", time: "Just now" },
  { action: "published", target: "OpenShift Retrieval Tool", suffix: "to Team Registry", time: "2m ago" },
  { action: "forked", target: "SRE Auto-Medic", time: "8m ago" },
  { action: "started", target: "Compliance Audit", time: "15m ago" },
  { action: "deployed", target: "Jira Story Generator", suffix: "v2.1", time: "32m ago" },
  { action: "shared", target: "RHEL Diagnostics MCP", suffix: "with team", time: "1h ago" },
  { action: "ran", target: "SRE Auto-Medic", suffix: "(42nd run!)", time: "1h ago" },
  { action: "added prompt", target: "Jira Summarizer", suffix: "to Team Registry", time: "2h ago" },
];

const DEMO_LEADERBOARD = [
  { name: "SRE Auto-Medic", runs: 42, users: 6, forks: 3, saved: "~18 hrs", pct: 100 },
  { name: "Compliance Auditor", runs: 28, users: 4, forks: 1, saved: "~8 hrs", pct: 67 },
  { name: "Jira Story Generator", runs: 15, users: 5, forks: 2, saved: "~3 hrs", pct: 36 },
  { name: "OpenShift Retrieval Agent", runs: 8, users: 3, forks: 0, saved: "~2 hrs", pct: 19 },
];

type AssetKind = "workflow" | "tool" | "mcp" | "template";

interface DemoAsset {
  name: string;
  kind: AssetKind;
  desc: string;
  authorIndex: number;
  runs: number;
  users: number;
  forks: number;
  visibility: "team" | "private";
  forkedFrom?: string;
}

const DEMO_ASSETS: DemoAsset[] = [
  { name: "SRE Auto-Medic", kind: "workflow", desc: "Autonomous incident triage: pulls logs, checks metrics, suggests runbooks, and can execute remediation steps.", authorIndex: 0, runs: 42, users: 6, forks: 3, visibility: "team" },
  { name: "Compliance Auditor", kind: "workflow", desc: "Scans infrastructure configs against CIS benchmarks, generates compliance reports and remediation tickets.", authorIndex: 3, runs: 28, users: 4, forks: 1, visibility: "team" },
  { name: "RHEL Diagnostics", kind: "mcp", desc: "MCP server for Red Hat Enterprise Linux diagnostics. Exposes sosreport analysis, systemd inspection, and kernel log parsing.", authorIndex: 5, runs: 19, users: 5, forks: 0, visibility: "team" },
  { name: "OpenShift Retrieval Agent", kind: "tool", desc: "RAG-powered retrieval over OpenShift documentation and internal runbooks. Supports contextual Q&A.", authorIndex: 1, runs: 8, users: 3, forks: 0, visibility: "team" },
  { name: "Jira Story Generator", kind: "template", desc: "Generates well-structured Jira stories from a natural language description. Includes acceptance criteria and subtasks.", authorIndex: 2, runs: 15, users: 5, forks: 2, visibility: "team", forkedFrom: "Alex K.'s Story Builder" },
  { name: "Log Anomaly Detector", kind: "workflow", desc: "Experimental workflow for detecting anomalous patterns in application logs using embedding similarity.", authorIndex: 4, runs: 2, users: 1, forks: 0, visibility: "private" },
];

interface DemoSession {
  name: string;
  blueprint: string;
  status: "running" | "idle";
  duration: string;
  participantCount: number;
}

const DEMO_SESSIONS: DemoSession[] = [
  { name: "Incident Triage — PROD-4521", blueprint: "SRE Auto-Medic", status: "running", duration: "12m", participantCount: 3 },
  { name: "Compliance Audit — Q1 Review", blueprint: "Compliance Auditor", status: "running", duration: "4m", participantCount: 1 },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function Avatar({ member, size = "sm" }: { member: MemberDisplay; size?: "xs" | "sm" | "md" }) {
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
  const [registryFilter, setRegistryFilter] = useState<"all" | AssetKind>("all");
  const [registryScope, setRegistryScope] = useState<"team" | "mine">("team");

  const { user } = useAuth();
  const { selectedTeam } = useView();

  const teamMembers = useMemo(() => {
    if (!selectedTeam?.members) return [];
    return selectedTeam.members.map((m, i) => buildMemberDisplay(m, i));
  }, [selectedTeam?.members]);

  const teamName = selectedTeam?.name || "Team";

  const urlRunId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("runId");
  }, []);

  const getActivityMember = (index: number): MemberDisplay => {
    if (teamMembers.length > 0) {
      return teamMembers[index % teamMembers.length];
    }
    return buildMemberDisplay(user?.username || "user", index);
  };

  const getAssetAuthor = (authorIndex: number): MemberDisplay => {
    if (teamMembers.length > 0) {
      return teamMembers[authorIndex % teamMembers.length];
    }
    return buildMemberDisplay(user?.username || "user", authorIndex);
  };

  const filteredAssets = DEMO_ASSETS.filter((a) => {
    if (registryScope === "mine" && a.visibility !== "private") return false;
    if (registryScope === "team" && a.visibility !== "team") return false;
    if (registryFilter !== "all" && a.kind !== registryFilter) return false;
    return true;
  });

  return (
    <>
      <Header title="AI Command Center" onToggleSidebar={() => {}} />

      <Tabs defaultValue="dashboard" className="flex-1 flex flex-col overflow-hidden">
        {/* Tab Navigation */}
        <div className="border-b border-gray-800 bg-background-surface px-6 flex items-center justify-between">
          <TabsList className="bg-transparent h-11 gap-1 p-0">
            <TabsTrigger
              value="dashboard"
              className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4"
            >
              <Activity className="w-3.5 h-3.5 mr-2" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger
              value="registry"
              className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4"
            >
              <Share2 className="w-3.5 h-3.5 mr-2" />
              Team Registry
            </TabsTrigger>
            <TabsTrigger
              value="collab-hub"
              className="data-[state=active]:bg-primary/15 data-[state=active]:text-primary rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-4"
            >
              <Rocket className="w-3.5 h-3.5 mr-2" />
              Collaboration Hub
              {DEMO_SESSIONS.filter((s) => s.status === "running").length > 0 && (
                <Badge className="ml-2 bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px] px-1.5 py-0">
                  {DEMO_SESSIONS.filter((s) => s.status === "running").length} live
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Team Indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-800 bg-background-card">
            <Users className="w-3.5 h-3.5 text-primary" />
            <span className="font-medium text-white text-xs">{teamName}</span>
            <span className="text-[10px] text-gray-500">
              {teamMembers.length} member{teamMembers.length !== 1 ? "s" : ""}
            </span>
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
                      <p className="text-xs text-gray-400">
                        Across {teamMembers.length} engineers running sessions on shared workflows
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-3xl font-extrabold text-emerald-400 tracking-tight">31 hrs</div>
                      <div className="text-[11px] text-gray-500">estimated saved</div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Stat Cards */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
                className="mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6"
              >
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Share2 className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaProjectDiagram className="text-primary mr-3 h-5 w-5" />Shared Workflows</span>}
                    value={14}
                    subtext="+3 this week"
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Users className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaUsers className="text-blue-400 mr-3 h-5 w-5" />Team Members</span>}
                    value={teamMembers.length}
                    subtext={`${Math.min(teamMembers.length, 6)} active today`}
                    iconColor="#60a5fa"
                    iconBgColor="rgba(96,165,250,.15)"
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Radio className="w-4 h-4" />}
                    title={<span className="flex items-center"><Zap className="text-emerald-400 mr-3 h-5 w-5" />Active Sessions</span>}
                    value={DEMO_SESSIONS.filter((s) => s.status === "running").length}
                    subtext="sessions open"
                    iconColor="#34d399"
                    iconBgColor="rgba(52,211,153,.15)"
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<TrendingUp className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaTrophy className="text-amber-400 mr-3 h-5 w-5" />Total Runs (7d)</span>}
                    value={58}
                    subtext="+22% vs last week"
                    iconColor="#fbbf24"
                    iconBgColor="rgba(251,191,36,.15)"
                  />
                </GlassPanel>
              </motion.div>

              {/* Live Sessions */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }} className="mb-6">
                <GlassPanel>
                  <Card className="bg-transparent border-0 shadow-none">
                    <CardHeader className="px-4 py-3 border-b border-gray-800/50">
                      <CardTitle className="text-base flex items-center gap-2">
                        <motion.div className="w-2 h-2 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
                        Live Collaboration Sessions
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      {DEMO_SESSIONS.filter((s) => s.status === "running").map((session, i) => (
                        <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/30 last:border-0 hover:bg-white/[.02] transition-colors">
                          <motion.div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-sm text-white truncate">{session.name}</div>
                            <div className="text-xs text-gray-500">{session.blueprint} · running for {session.duration}</div>
                          </div>
                          <div className="flex items-center -space-x-1.5">
                            {teamMembers.slice(0, Math.min(session.participantCount, 3)).map((p) => (
                              <div key={p.id} className="ring-2 ring-background-card rounded-full"><Avatar member={p} size="xs" /></div>
                            ))}
                          </div>
                          <Button size="sm" className="bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/20 text-xs h-7 px-3">
                            Join
                          </Button>
                        </div>
                      ))}
                      {DEMO_SESSIONS.filter((s) => s.status === "running").length === 0 && (
                        <div className="px-4 py-6 text-center text-gray-500 text-sm">
                          No live sessions. Start one from the Collaboration Hub tab.
                        </div>
                      )}
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
                      {DEMO_LEADERBOARD.map((item, i) => {
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
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: 0.25 }}
              className="w-[280px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex"
            >
              <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
                <motion.div className="w-2 h-2 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
                <span className="font-semibold text-sm text-white">Live Activity</span>
              </div>
              <div className="flex-1 overflow-y-auto">
                {DEMO_ACTIVITY.map((evt, i) => {
                  const member = getActivityMember(i);
                  return (
                    <div key={i} className="flex gap-2.5 px-4 py-2.5 border-b border-gray-800/40 hover:bg-white/[.02] transition-colors">
                      <Avatar member={member} size="xs" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs leading-relaxed">
                          <span className="font-semibold text-gray-200">{member.name}</span>{" "}
                          <span className="text-gray-500">{evt.action} </span>
                          <span className="text-primary font-medium">{evt.target}</span>
                          {evt.suffix && <span className="text-gray-500"> {evt.suffix}</span>}
                        </p>
                        <p className="text-[10px] text-gray-600 mt-0.5">{evt.time}</p>
                      </div>
                    </div>
                  );
                })}
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
                  <button
                    key={k}
                    onClick={() => setRegistryFilter(k)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
                      registryFilter === k ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"
                    }`}
                  >
                    {k === "all" ? "All" : k === "mcp" ? "MCPs" : `${k}s`}
                  </button>
                ))}
              </div>

              <div className="flex bg-background-card border border-gray-800 rounded-lg p-0.5 gap-0.5">
                <button
                  onClick={() => setRegistryScope("team")}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors truncate max-w-[160px] ${
                    registryScope === "team" ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  Team Assets
                </button>
                <button
                  onClick={() => setRegistryScope("mine")}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    registryScope === "mine" ? "bg-primary/15 text-primary" : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  My Assets
                </button>
              </div>

              <div className="flex-1 min-w-[200px] relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" />
                <input
                  type="text"
                  placeholder="Search team assets..."
                  className="w-full bg-background-card border border-gray-800 rounded-lg py-2 pl-9 pr-3 text-xs text-white placeholder:text-gray-600 outline-none focus:border-primary/50 transition-colors"
                />
              </div>
            </div>

            {/* Asset Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              <AnimatePresence mode="popLayout">
                {filteredAssets.map((asset) => {
                  const author = getAssetAuthor(asset.authorIndex);
                  return (
                    <motion.div
                      key={asset.name}
                      layout
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Card className={`border-gray-800 hover:border-gray-700 transition-all cursor-pointer group ${asset.visibility === "private" ? "opacity-60" : ""}`}>
                        <CardContent className="p-5">
                          <div className="flex items-start justify-between mb-3">
                            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${ASSET_BADGE_STYLES[asset.kind]}`}>
                              {asset.kind}
                            </span>
                            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                              {asset.visibility === "team" ? (
                                <><Eye className="w-3 h-3" />Team</>
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
                              <Avatar member={author} size="xs" />
                              <span className="text-[11px] text-gray-500">{author.name}</span>
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
                  );
                })}
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

        {/* ══════════════ MISSION CONTROL TAB ══════════════ */}
        <TabsContent value="collab-hub" className="flex-1 overflow-hidden mt-0">
          <StreamingDataProvider>
            <CollaborationHubView
              runId={urlRunId}
              teamMembers={teamMembers}
              teamName={teamName}
            />
          </StreamingDataProvider>
        </TabsContent>
      </Tabs>
    </>
  );
}
