import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView, TeamInfo } from "@/contexts/ViewContext";
import {
  createTeam,
  updateTeam,
  deleteTeam,
  searchDirectoryUsers,
  DirectoryUser,
} from "@/api/teams";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { X, Crown, Trash2, Users, Loader2, Search } from "lucide-react";
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
  const { user, accessToken } = useAuth();
  const { refreshTeams } = useView();
  const [teamName, setTeamName] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const [suggestions, setSuggestions] = useState<DirectoryUser[]>([]);
  const [searching, setSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchError, setSearchError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchIdRef = useRef(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
      setMemberSearch("");
      setSuggestions([]);
      setError("");
      setSearchError("");
      setDropdownOpen(false);
      searchIdRef.current = 0;
    }
  }, [open, team, user?.username]);

  useEffect(() => {
    if (!dropdownOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  const handleSearchChange = useCallback(
    (value: string) => {
      setMemberSearch(value);
      setSearchError("");

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (value.trim().length < 2) {
        setSuggestions([]);
        setDropdownOpen(false);
        setSearching(false);
        return;
      }

      setSearching(true);
      setDropdownOpen(true);

      debounceRef.current = setTimeout(async () => {
        const id = ++searchIdRef.current;
        try {
          const results = await searchDirectoryUsers(value.trim(), 10, accessToken);
          if (id !== searchIdRef.current) return;
          const filtered = results.filter((u) => !members.includes(u.user_id));
          setSuggestions(filtered);
        } catch (err: any) {
          if (id !== searchIdRef.current) return;
          setSuggestions([]);
          const status = err?.response?.status;
          if (status === 501) {
            setSearchError("Directory provider is not configured");
          } else {
            setSearchError("Search failed — try again");
          }
        } finally {
          if (id === searchIdRef.current) setSearching(false);
        }
      }, 300);
    },
    [members, accessToken],
  );

  const addMemberFromDirectory = (dirUser: DirectoryUser) => {
    if (!members.includes(dirUser.user_id)) {
      setMembers([...members, dirUser.user_id]);
    }
    setMemberSearch("");
    setSuggestions([]);
    setDropdownOpen(false);
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
              <div className="relative mt-1.5">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
                  <Input
                    ref={inputRef}
                    value={memberSearch}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    onFocus={() => {
                      if (suggestions.length > 0 || searching) setDropdownOpen(true);
                    }}
                    placeholder="Search people by name or username…"
                    className="pl-9 bg-background-dark border-gray-700 text-gray-100 placeholder:text-gray-500"
                  />
                  {searching && (
                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
                  )}
                </div>

                {dropdownOpen && memberSearch.trim().length >= 2 && (
                  <div
                    ref={dropdownRef}
                    className="absolute z-[50] w-full mt-1 max-h-[220px] overflow-y-auto rounded-md border border-gray-700 bg-black shadow-lg"
                  >
                    {searching ? (
                      <div className="flex items-center justify-center py-4 text-sm text-gray-400">
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Searching…
                      </div>
                    ) : searchError ? (
                      <div className="px-3 py-4 text-sm text-amber-400 text-center">
                        {searchError}
                      </div>
                    ) : suggestions.length === 0 ? (
                      <div className="px-3 py-4 text-sm text-gray-400 text-center">
                        No users found
                      </div>
                    ) : (
                      suggestions.map((u) => (
                        <button
                          key={u.user_id}
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => addMemberFromDirectory(u)}
                          className="w-full flex flex-col px-3 py-2 text-left hover:bg-white/10 transition-colors cursor-pointer"
                        >
                          <span className="text-sm text-gray-100">{u.display_name}</span>
                          <span className="text-xs text-gray-400">
                            {u.username}{u.email ? ` · ${u.email}` : ""}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
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
