import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView, TeamInfo } from "@/contexts/ViewContext";
import { createTeam, updateTeam, deleteTeam } from "@/api/teams";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { X, Crown, Trash2, Users, Loader2 } from "lucide-react";
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
import UserDirectorySearch from "@/components/shared/UserDirectorySearch";
import type { DirectoryUser, DirectoryGroup } from "@/api/directory";

interface TeamSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: TeamInfo | null;
}

export default function TeamSettingsModal({ open, onOpenChange, team }: TeamSettingsModalProps) {
  const { user, accessToken } = useAuth();
  const { refreshTeams } = useView();
  const [teamName, setTeamName] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [expandingGroup, setExpandingGroup] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [searchResetKey, setSearchResetKey] = useState(0);

  const isEditing = !!team;

  useEffect(() => {
    if (open) {
      if (team) {
        setTeamName(team.name);
        setMembers([...team.members]);
      } else {
        setTeamName("");
        setMembers(user?.username ? [user.username] : []);
      }
      setError("");
      setSearchResetKey((k) => k + 1);
    }
  }, [open, team, user?.username]);

  const addMemberFromDirectory = (dirUser: DirectoryUser) => {
    if (!members.includes(dirUser.user_id)) {
      setMembers((prev) => [...prev, dirUser.user_id]);
    }
    setError("");
    setSearchResetKey((k) => k + 1);
  };

  const addGroupMembers = async (group: DirectoryGroup) => {
    setExpandingGroup(true);
    setError("");
    try {
      const newMembers = group.members.filter((uid) => !members.includes(uid));
      if (newMembers.length === 0) {
        setError(`All members of "${group.name}" are already in this team`);
      } else {
        setMembers((prev) => [...prev, ...newMembers]);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to expand group");
    } finally {
      setExpandingGroup(false);
      setSearchResetKey((k) => k + 1);
    }
  };

  const removeMember = (username: string) => {
    if (isEditing && username === team.created_by) return;
    if (!isEditing && username === user?.username) return;
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
      if (isEditing) {
        await updateTeam(team.id, { name: teamName.trim(), members });
      } else {
        await createTeam(teamName.trim(), user!.username, members);
      }
      await refreshTeams();
      onOpenChange(false);
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || "Operation failed";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!team) return;
    try {
      await deleteTeam(team.id);
      await refreshTeams();
      setDeleteConfirmOpen(false);
      onOpenChange(false);
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || "Failed to delete team");
      console.error("Failed to delete team:", err);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="bg-background-card border-gray-800 sm:max-w-md overflow-visible">          
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              {isEditing ? "Team Settings" : "Create New Team"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div>
              <Label htmlFor="modal-team-name" className="text-sm text-gray-400">Team Name</Label>
              <Input
                id="modal-team-name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder="e.g. Platform Engineering"
                className="mt-1.5 bg-background-dark border-gray-700"
              />
            </div>

            <div>
              <Label className="text-sm text-gray-400">Members</Label>
              <div className="mt-1.5">
                <UserDirectorySearch
                  key={searchResetKey}
                  onSelect={addMemberFromDirectory}
                  onSelectGroup={addGroupMembers}
                  excludeUserIds={members}
                  accessToken={accessToken}
                  inputClassName="bg-background-dark border-gray-700 text-gray-100 placeholder:text-gray-500"
                />
              </div>

              {expandingGroup && (
                <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Adding group members…
                </div>
              )}

              {members.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {members.map((m) => {
                    const isCreator = isEditing ? m === team.created_by : m === user?.username;
                    return (
                      <span
                        key={m}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-white/5 text-gray-300 border border-gray-800"
                      >
                        {isCreator && <Crown className="w-3 h-3 text-amber-400" />}
                        {m}
                        {!isCreator && (
                          <button onClick={() => removeMember(m)} className="ml-0.5 hover:text-red-400 transition-colors">
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

            <div className="flex items-center justify-between pt-3 border-t border-gray-800">
              {isEditing && team.created_by === user?.username ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleteConfirmOpen(true)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                  Delete Team
                </Button>
              ) : (
                <div />
              )}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)} className="border-gray-700">
                  Cancel
                </Button>
                <Button className="bg-primary" onClick={handleSubmit} disabled={saving || expandingGroup}>
                  {saving ? "Saving..." : isEditing ? "Save Changes" : "Create Team"}
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Team</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{team?.name}</strong>? This action cannot be undone.
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
    </>
  );
}
