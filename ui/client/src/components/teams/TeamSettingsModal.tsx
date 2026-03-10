import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView, TeamInfo } from "@/contexts/ViewContext";
import { createTeam, updateTeam, deleteTeam } from "@/api/teams";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { UserPlus, X, Crown, Trash2, Users } from "lucide-react";
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

interface TeamSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: TeamInfo | null;
}

export default function TeamSettingsModal({ open, onOpenChange, team }: TeamSettingsModalProps) {
  const { user } = useAuth();
  const { refreshTeams, setSelectedTeam, teams } = useView();
  const [teamName, setTeamName] = useState("");
  const [memberInput, setMemberInput] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

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
      setMemberInput("");
      setError("");
    }
  }, [open, team, user?.username]);

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
      console.error("Failed to delete team:", err);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="bg-background-card border-gray-800 sm:max-w-md">
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
              <div className="flex gap-2 mt-1.5">
                <Input
                  value={memberInput}
                  onChange={(e) => setMemberInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addMember(); } }}
                  placeholder="Username — press Enter to add"
                  className="bg-background-dark border-gray-700"
                />
                <Button type="button" variant="outline" onClick={addMember} className="shrink-0 border-gray-700">
                  <UserPlus className="w-4 h-4" />
                </Button>
              </div>

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
                <Button className="bg-primary" onClick={handleSubmit} disabled={saving}>
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
