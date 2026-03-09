import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FaUsers, FaKey, FaRobot, FaCog, FaLock, FaInfoCircle } from "react-icons/fa";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { useAuth } from "@/contexts/AuthContext";
import { useView, TeamInfo } from "@/contexts/ViewContext";
import { createTeam, updateTeam, deleteTeam } from "@/api/teams";
import { Users, Plus, Pencil, Trash2, X, UserPlus, Crown } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

function TeamManagementTab() {
  const { user } = useAuth();
  const { teams, refreshTeams } = useView();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<TeamInfo | null>(null);
  const [deleteConfirmTeam, setDeleteConfirmTeam] = useState<TeamInfo | null>(null);
  const [teamName, setTeamName] = useState("");
  const [memberInput, setMemberInput] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const resetForm = () => {
    setTeamName("");
    setMemberInput("");
    setMembers([]);
    setError("");
    setEditingTeam(null);
  };

  const openCreate = () => {
    resetForm();
    if (user?.username) {
      setMembers([user.username]);
    }
    setDialogOpen(true);
  };

  const openEdit = (team: TeamInfo) => {
    setEditingTeam(team);
    setTeamName(team.name);
    setMembers([...team.members]);
    setMemberInput("");
    setError("");
    setDialogOpen(true);
  };

  const addMember = () => {
    const username = memberInput.trim();
    if (!username) return;
    if (members.includes(username)) {
      setError(`"${username}" is already a member`);
      return;
    }
    setMembers([...members, username]);
    setMemberInput("");
    setError("");
  };

  const removeMember = (username: string) => {
    if (editingTeam && username === editingTeam.created_by) return;
    if (!editingTeam && username === user?.username) return;
    setMembers(members.filter((m) => m !== username));
  };

  const handleSubmit = async () => {
    if (!teamName.trim()) {
      setError("Team name is required");
      return;
    }
    if (members.length === 0) {
      setError("At least one member is required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingTeam) {
        await updateTeam(editingTeam.id, { name: teamName.trim(), members });
      } else {
        await createTeam(teamName.trim(), user!.username, members);
      }
      await refreshTeams();
      setDialogOpen(false);
      resetForm();
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || "Operation failed";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirmTeam) return;
    try {
      await deleteTeam(deleteConfirmTeam.id);
      await refreshTeams();
    } catch (err: any) {
      console.error("Failed to delete team:", err);
    } finally {
      setDeleteConfirmTeam(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-heading font-semibold">Your Teams</h3>
          <p className="text-sm text-gray-400 mt-1">
            Create and manage teams to collaborate on workflows and resources
          </p>
        </div>
        <Button className="bg-primary" onClick={openCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Create Team
        </Button>
      </div>

      {teams.length === 0 ? (
        <Card className="bg-background-card shadow-card border-gray-800">
          <CardContent className="p-12 text-center">
            <Users className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h4 className="text-lg font-medium text-gray-300 mb-2">No teams yet</h4>
            <p className="text-sm text-gray-500 mb-6">
              Create a team to start collaborating with others on shared workflows and resources.
            </p>
            <Button className="bg-primary" onClick={openCreate}>
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Team
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {teams.map((team) => (
            <Card key={team.id} className="bg-background-card shadow-card border-gray-800 hover:border-gray-700 transition-colors">
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-primary/15 flex items-center justify-center">
                      <Users className="w-4 h-4 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white">{team.name}</h4>
                      <p className="text-xs text-gray-500">{team.members.length} member{team.members.length !== 1 ? "s" : ""}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => openEdit(team)}
                      className="p-1.5 rounded-md text-gray-500 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    {team.created_by === user?.username && (
                      <button
                        onClick={() => setDeleteConfirmTeam(team)}
                        className="p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 mt-3">
                  {team.members.map((member) => (
                    <span
                      key={member}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-white/5 text-gray-300"
                    >
                      {member === team.created_by && <Crown className="w-3 h-3 text-amber-400" />}
                      {member}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) { setDialogOpen(false); resetForm(); } }}>
        <DialogContent className="bg-background-card border-gray-800 sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingTeam ? "Edit Team" : "Create New Team"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div>
              <Label htmlFor="team-name" className="text-sm">Team Name</Label>
              <Input
                id="team-name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder="e.g. Platform Engineering"
                className="mt-1 bg-background-dark"
              />
            </div>

            <div>
              <Label className="text-sm">Members</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  value={memberInput}
                  onChange={(e) => setMemberInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addMember(); } }}
                  placeholder="Type a username and press Enter"
                  className="bg-background-dark"
                />
                <Button type="button" variant="outline" onClick={addMember} className="shrink-0">
                  <UserPlus className="w-4 h-4" />
                </Button>
              </div>

              {members.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {members.map((m) => {
                    const isCreator = editingTeam
                      ? m === editingTeam.created_by
                      : m === user?.username;
                    return (
                      <span
                        key={m}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-white/5 text-gray-300"
                      >
                        {isCreator && <Crown className="w-3 h-3 text-amber-400" />}
                        {m}
                        {!isCreator && (
                          <button onClick={() => removeMember(m)} className="ml-0.5 hover:text-red-400">
                            <X className="w-3 h-3" />
                          </button>
                        )}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>

            {error && (
              <p className="text-sm text-red-400">{error}</p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>
                Cancel
              </Button>
              <Button className="bg-primary" onClick={handleSubmit} disabled={saving}>
                {saving ? "Saving..." : editingTeam ? "Save Changes" : "Create Team"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteConfirmTeam} onOpenChange={(open) => { if (!open) setDeleteConfirmTeam(null); }}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Team</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{deleteConfirmTeam?.name}</strong>? This action cannot be undone.
              Resources and workflows created under this team will remain but won't be accessible through the team view.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Configuration() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Configuration Manager" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Tabs defaultValue="teams" className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger value="teams" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                  <FaUsers className="mr-2" />
                  Teams
                </TabsTrigger>
                <TabsTrigger value="settings" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                  <FaCog className="mr-2" />
                  Settings
                </TabsTrigger>
                <TabsTrigger value="users" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                  <FaUsers className="mr-2" />
                  User Management
                </TabsTrigger>
                <TabsTrigger value="embedding" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                  <FaRobot className="mr-2" />
                  Embedding Settings
                </TabsTrigger>
              </TabsList>

              <TabsContent value="teams">
                <TeamManagementTab />
              </TabsContent>
              
              <TabsContent value="settings">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">General Settings</h3>
                      
                      <div className="space-y-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <Label htmlFor="dark-mode" className="text-base">Dark Mode</Label>
                            <p className="text-xs text-gray-400 mt-1">Enable dark mode for the interface</p>
                          </div>
                          <Switch id="dark-mode" defaultChecked />
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <div>
                            <Label htmlFor="notifications" className="text-base">Notifications</Label>
                            <p className="text-xs text-gray-400 mt-1">Receive notifications for pipeline events</p>
                          </div>
                          <Switch id="notifications" defaultChecked />
                        </div>
                        
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="auto-sync" className="text-base">Auto-Sync Interval</Label>
                            <span className="text-sm">30 minutes</span>
                          </div>
                          <Slider id="auto-sync" defaultValue={[30]} max={120} step={5} />
                          <p className="text-xs text-gray-400">How often data sources will be automatically synchronized</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">API Configuration</h3>
                      
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="api-key" className="text-sm">API Key</Label>
                          <div className="flex mt-1">
                            <Input id="api-key" type="password" value="••••••••••••••••••••" readOnly className="rounded-r-none bg-background-dark" />
                            <Button variant="outline" className="rounded-l-none border-l-0">
                              <FaKey className="mr-2" />
                              <span>Generate</span>
                            </Button>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">Used for programmatic access</p>
                        </div>
                        
                        <div>
                          <Label htmlFor="webhook-url" className="text-sm">Webhook URL</Label>
                          <div className="flex mt-1">
                            <Input id="webhook-url" value="https://api.rag.pro/webhooks/events" readOnly className="rounded-r-none bg-background-dark" />
                            <Button variant="outline" className="rounded-l-none border-l-0">Copy</Button>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">Receive real-time updates via webhooks</p>
                        </div>
                        
                        <div className="flex items-center justify-between pt-2">
                          <div>
                            <Label htmlFor="api-access" className="text-base">API Access</Label>
                            <p className="text-xs text-gray-400 mt-1">Enable API access for this project</p>
                          </div>
                          <Switch id="api-access" defaultChecked />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Storage Settings</h3>
                      
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="retention" className="text-sm">Data Retention Period</Label>
                          <div className="flex items-center space-x-3 mt-2">
                            <Button variant={true ? "default" : "outline"} size="sm" className={true ? "bg-primary" : ""}>30 Days</Button>
                            <Button variant={false ? "default" : "outline"} size="sm" className={false ? "bg-primary" : ""}>90 Days</Button>
                            <Button variant={false ? "default" : "outline"} size="sm" className={false ? "bg-primary" : ""}>1 Year</Button>
                            <Button variant={false ? "default" : "outline"} size="sm" className={false ? "bg-primary" : ""}>Forever</Button>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">How long processed data will be stored</p>
                        </div>
                        
                        <div className="pt-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="compress-data" className="text-base">Compress Data</Label>
                              <p className="text-xs text-gray-400 mt-1">Save storage space by compressing stored data</p>
                            </div>
                            <Switch id="compress-data" defaultChecked />
                          </div>
                        </div>
                        
                        <div className="pt-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="backup" className="text-base">Auto Backup</Label>
                              <p className="text-xs text-gray-400 mt-1">Automatically back up settings and configurations</p>
                            </div>
                            <Switch id="backup" defaultChecked />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Security Settings</h3>
                      
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <Label htmlFor="2fa" className="text-base">Two-Factor Authentication</Label>
                            <p className="text-xs text-gray-400 mt-1">Increase account security with 2FA</p>
                          </div>
                          <Switch id="2fa" />
                        </div>
                        
                        <div className="flex items-center justify-between pt-2">
                          <div>
                            <Label htmlFor="session-timeout" className="text-base">Session Timeout</Label>
                            <p className="text-xs text-gray-400 mt-1">Automatically log out after inactivity</p>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Input 
                              id="session-timeout" 
                              className="w-16 text-center bg-background-dark" 
                              type="number" 
                              min={5} 
                              max={120} 
                              defaultValue={30}
                            />
                            <span className="text-sm">min</span>
                          </div>
                        </div>
                        
                        <div className="pt-2">
                          <Button variant="outline" className="w-full mt-4">
                            <FaLock className="mr-2" />
                            <span>Update Security Settings</span>
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
              
              <TabsContent value="users">
                <div className="grid grid-cols-1 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-heading font-semibold">Team Members</h3>
                        <Button className="bg-primary">Add User</Button>
                      </div>
                      
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="border-b border-gray-800">
                              <th className="text-left py-2 font-medium text-sm text-gray-400">User</th>
                              <th className="text-left py-2 font-medium text-sm text-gray-400">Email</th>
                              <th className="text-left py-2 font-medium text-sm text-gray-400">Role</th>
                              <th className="text-left py-2 font-medium text-sm text-gray-400">Status</th>
                              <th className="text-right py-2 font-medium text-sm text-gray-400">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-gray-800">
                              <td className="py-3 flex items-center space-x-3">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center">
                                  <span className="text-white text-xs font-medium">AK</span>
                                </div>
                                <span>Alex Kim</span>
                              </td>
                              <td className="py-3 text-gray-300">alex@example.com</td>
                              <td className="py-3">
                                <Badge className="bg-primary bg-opacity-20 text-primary">Administrator</Badge>
                              </td>
                              <td className="py-3">
                                <Badge className="bg-success bg-opacity-20 text-success">Active</Badge>
                              </td>
                              <td className="py-3 text-right">
                                <Button variant="ghost" size="sm">Edit</Button>
                              </td>
                            </tr>
                            <tr className="border-b border-gray-800">
                              <td className="py-3 flex items-center space-x-3">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-secondary to-accent flex items-center justify-center">
                                  <span className="text-white text-xs font-medium">JD</span>
                                </div>
                                <span>Jane Doe</span>
                              </td>
                              <td className="py-3 text-gray-300">jane@example.com</td>
                              <td className="py-3">
                                <Badge className="bg-secondary bg-opacity-20 text-secondary">Editor</Badge>
                              </td>
                              <td className="py-3">
                                <Badge className="bg-success bg-opacity-20 text-success">Active</Badge>
                              </td>
                              <td className="py-3 text-right">
                                <Button variant="ghost" size="sm">Edit</Button>
                              </td>
                            </tr>
                            <tr>
                              <td className="py-3 flex items-center space-x-3">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-accent to-primary flex items-center justify-center">
                                  <span className="text-white text-xs font-medium">MS</span>
                                </div>
                                <span>Mike Smith</span>
                              </td>
                              <td className="py-3 text-gray-300">mike@example.com</td>
                              <td className="py-3">
                                <Badge className="bg-accent bg-opacity-20 text-accent">Viewer</Badge>
                              </td>
                              <td className="py-3">
                                <Badge className="bg-gray-700 text-gray-400">Invited</Badge>
                              </td>
                              <td className="py-3 text-right">
                                <Button variant="ghost" size="sm">Edit</Button>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Role Permissions</h3>
                      
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="border-b border-gray-800">
                              <th className="text-left py-2 font-medium text-sm text-gray-400">Permission</th>
                              <th className="text-center py-2 font-medium text-sm text-gray-400">
                                Administrator
                                <Badge className="ml-2 bg-primary bg-opacity-20 text-primary text-xs">1</Badge>
                              </th>
                              <th className="text-center py-2 font-medium text-sm text-gray-400">
                                Editor
                                <Badge className="ml-2 bg-secondary bg-opacity-20 text-secondary text-xs">1</Badge>
                              </th>
                              <th className="text-center py-2 font-medium text-sm text-gray-400">
                                Viewer
                                <Badge className="ml-2 bg-accent bg-opacity-20 text-accent text-xs">1</Badge>
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-gray-800">
                              <td className="py-3">View Dashboards</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">✓</td>
                            </tr>
                            <tr className="border-b border-gray-800">
                              <td className="py-3">Create Projects</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">-</td>
                            </tr>
                            <tr className="border-b border-gray-800">
                              <td className="py-3">Manage Data Sources</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">-</td>
                            </tr>
                            <tr className="border-b border-gray-800">
                              <td className="py-3">Manage Users</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">-</td>
                              <td className="py-3 text-center">-</td>
                            </tr>
                            <tr>
                              <td className="py-3">System Settings</td>
                              <td className="py-3 text-center">✓</td>
                              <td className="py-3 text-center">-</td>
                              <td className="py-3 text-center">-</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      
                      <div className="mt-4 text-center">
                        <Button variant="outline">Edit Role Permissions</Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
              
              <TabsContent value="embedding">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Model Selection</h3>
                      
                      <div className="space-y-4">
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800 cursor-pointer hover:border-primary transition-colors">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center">
                                <h4 className="font-medium">OpenAI Embeddings</h4>
                                <Badge className="ml-2 bg-primary bg-opacity-20 text-primary">Active</Badge>
                              </div>
                              <p className="text-xs text-gray-400 mt-1">text-embedding-3-large: Best quality for semantic search</p>
                            </div>
                            <Tooltip>
                              <Tooltip.Trigger asChild>
                                <div className="text-gray-400">
                                  <FaInfoCircle />
                                </div>
                              </Tooltip.Trigger>
                              <Tooltip.Content>
                                <p className="w-64">1536-dimensional embeddings suitable for semantic search, clustering, and more.</p>
                              </Tooltip.Content>
                            </Tooltip>
                          </div>
                          
                          <div className="mt-3 pt-3 border-t border-gray-800">
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-gray-400">Performance</span>
                              <div className="flex items-center">
                                <div className="w-16 h-2 bg-gray-800 rounded-full mr-2 overflow-hidden">
                                  <div className="h-full bg-primary" style={{ width: '90%' }}></div>
                                </div>
                                <span>90%</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800 cursor-pointer hover:border-primary transition-colors">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center">
                                <h4 className="font-medium">Cohere Embeddings</h4>
                                <Badge className="ml-2 bg-gray-700 text-gray-400">Available</Badge>
                              </div>
                              <p className="text-xs text-gray-400 mt-1">embed-english-v3.0: Multilingual support</p>
                            </div>
                            <Tooltip>
                              <Tooltip.Trigger asChild>
                                <div className="text-gray-400">
                                  <FaInfoCircle />
                                </div>
                              </Tooltip.Trigger>
                              <Tooltip.Content>
                                <p className="w-64">Optimized for multilingual content with strong cross-language retrieval capabilities.</p>
                              </Tooltip.Content>
                            </Tooltip>
                          </div>
                          
                          <div className="mt-3 pt-3 border-t border-gray-800">
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-gray-400">Performance</span>
                              <div className="flex items-center">
                                <div className="w-16 h-2 bg-gray-800 rounded-full mr-2 overflow-hidden">
                                  <div className="h-full bg-secondary" style={{ width: '85%' }}></div>
                                </div>
                                <span>85%</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800 cursor-pointer hover:border-primary transition-colors">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center">
                                <h4 className="font-medium">Hugging Face Embeddings</h4>
                                <Badge className="ml-2 bg-gray-700 text-gray-400">Available</Badge>
                              </div>
                              <p className="text-xs text-gray-400 mt-1">all-MiniLM-L6-v2: Lightweight and efficient</p>
                            </div>
                            <Tooltip>
                              <Tooltip.Trigger asChild>
                                <div className="text-gray-400">
                                  <FaInfoCircle />
                                </div>
                              </Tooltip.Trigger>
                              <Tooltip.Content>
                                <p className="w-64">Smaller model size with good performance for resource-constrained environments.</p>
                              </Tooltip.Content>
                            </Tooltip>
                          </div>
                          
                          <div className="mt-3 pt-3 border-t border-gray-800">
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-gray-400">Performance</span>
                              <div className="flex items-center">
                                <div className="w-16 h-2 bg-gray-800 rounded-full mr-2 overflow-hidden">
                                  <div className="h-full bg-accent" style={{ width: '75%' }}></div>
                                </div>
                                <span>75%</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Embedding Parameters</h3>
                      
                      <div className="space-y-6">
                        <div>
                          <Label htmlFor="chunk-size" className="text-sm">Chunk Size</Label>
                          <div className="flex items-center space-x-2 mt-2">
                            <Input 
                              id="chunk-size" 
                              className="w-24 text-center bg-background-dark" 
                              type="number" 
                              min={100} 
                              max={2048} 
                              defaultValue={512}
                            />
                            <span className="text-sm">tokens</span>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">Size of text chunks for processing</p>
                          
                          <div className="mt-4 h-1.5 w-full bg-background-dark rounded-full overflow-hidden">
                            <div className="h-full bg-primary" style={{ width: '50%' }}></div>
                          </div>
                          <div className="flex justify-between text-xs text-gray-400 mt-1">
                            <span>Smaller (faster, less context)</span>
                            <span>Larger (slower, more context)</span>
                          </div>
                        </div>
                        
                        <div className="pt-2">
                          <Label htmlFor="overlap" className="text-sm">Chunk Overlap</Label>
                          <div className="flex items-center space-x-2 mt-2">
                            <Input 
                              id="overlap" 
                              className="w-24 text-center bg-background-dark" 
                              type="number" 
                              min={0} 
                              max={256} 
                              defaultValue={50}
                            />
                            <span className="text-sm">tokens</span>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">Overlap between consecutive chunks</p>
                        </div>
                        
                        <div className="pt-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="metadata" className="text-base">Include Metadata</Label>
                              <p className="text-xs text-gray-400 mt-1">Store document metadata with embeddings</p>
                            </div>
                            <Switch id="metadata" defaultChecked />
                          </div>
                        </div>
                        
                        <div className="pt-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="preprocessing" className="text-base">Text Preprocessing</Label>
                              <p className="text-xs text-gray-400 mt-1">Clean and normalize text before embedding</p>
                            </div>
                            <Switch id="preprocessing" defaultChecked />
                          </div>
                        </div>
                        
                        <div className="pt-2">
                          <Button className="w-full bg-primary">Apply Parameters</Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-background-card shadow-card border-gray-800 lg:col-span-2">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">Test Embedding</h3>
                      
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="test-text" className="text-sm">Sample Text</Label>
                          <textarea 
                            id="test-text" 
                            rows={4} 
                            className="w-full mt-2 p-3 rounded-md border border-gray-800 bg-background-dark resize-none"
                            placeholder="Enter text to test embedding generation..."
                            defaultValue="RAG Pro is a modern data pipeline management tool that makes complex data operations feel intuitive and exciting."
                          ></textarea>
                        </div>
                        
                        <div className="flex justify-end">
                          <Button className="bg-primary">Generate Embedding</Button>
                        </div>
                        
                        <div className="bg-background-dark p-4 rounded-md border border-gray-800">
                          <div className="flex items-center justify-between mb-3">
                            <span className="font-medium">Embedding Result</span>
                            <Button variant="outline" size="sm">Copy</Button>
                          </div>
                          
                          <div className="font-mono text-xs text-gray-400 overflow-auto max-h-36">
                            <p>[0.023, -0.112, 0.045, 0.078, -0.091, ...]</p>
                            <p className="mt-2 text-gray-500">Showing first 5 of 1536 dimensions</p>
                          </div>
                          
                          <div className="mt-4 pt-4 border-t border-gray-800">
                            <h4 className="font-medium mb-2">Embedding Quality Metrics</h4>
                            <div className="grid grid-cols-3 gap-4">
                              <div>
                                <p className="text-xs text-gray-400">Dimensionality</p>
                                <p className="font-medium">1536</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">L2 Norm</p>
                                <p className="font-medium">1.000</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Processing Time</p>
                                <p className="font-medium">124ms</p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>
          </motion.div>
        </main>
        
        <StatusBar />
      </div>
    </div>
  );
}
