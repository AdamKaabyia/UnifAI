import { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  DirectoryUser,
  searchDirectoryUsers,
  getDirectoryStatus,
} from '@/api/directory';

export type { DirectoryUser };

interface UserDirectorySearchProps {
  onSelect: (user: DirectoryUser) => void;
  onInputChange?: (value: string) => void;
  excludeUserIds?: string[];
  placeholder?: string;
  clearOnSelect?: boolean;
  accessToken?: string | null;
  inputClassName?: string;
}

export default function UserDirectorySearch({
  onSelect,
  onInputChange,
  excludeUserIds = [],
  placeholder,
  clearOnSelect = true,
  accessToken,
  inputClassName,
}: UserDirectorySearchProps) {
  const [directoryEnabled, setDirectoryEnabled] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DirectoryUser[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchError, setSearchError] = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchIdRef = useRef(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDirectoryStatus()
      .then(({ enabled }) => setDirectoryEnabled(enabled))
      .catch(() => setDirectoryEnabled(false));
  }, []);

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
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value);
      setSearchError('');
      onInputChange?.(value);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (!directoryEnabled || value.trim().length < 2) {
        setResults([]);
        setDropdownOpen(false);
        setIsSearching(false);
        return;
      }

      setIsSearching(true);
      setDropdownOpen(true);

      debounceRef.current = setTimeout(async () => {
        const id = ++searchIdRef.current;
        try {
          const users = await searchDirectoryUsers(value.trim(), 10, accessToken);
          if (id !== searchIdRef.current) return;
          const filtered = users.filter((u) => !excludeUserIds.includes(u.user_id));
          setResults(filtered);
        } catch (err: any) {
          if (id !== searchIdRef.current) return;
          setResults([]);
          const status = err?.response?.status;
          if (status === 501) {
            setSearchError('Directory provider is not configured');
          } else {
            setSearchError('Search failed — try again');
          }
        } finally {
          if (id === searchIdRef.current) setIsSearching(false);
        }
      }, 300);
    },
    [directoryEnabled, excludeUserIds, accessToken, onInputChange],
  );

  const handleSelect = (user: DirectoryUser) => {
    onSelect(user);
    if (clearOnSelect) {
      setQuery('');
    } else {
      setQuery(user.username);
    }
    setResults([]);
    setDropdownOpen(false);
  };

  const defaultPlaceholder = directoryEnabled
    ? 'Search people by name or username\u2026'
    : 'Enter username';

  return (
    <div className="relative">
      <div className="relative">
        {directoryEnabled && (
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
        )}
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (results.length > 0 || isSearching) setDropdownOpen(true);
          }}
          placeholder={placeholder ?? defaultPlaceholder}
          className={`${directoryEnabled ? 'pl-9' : ''} ${inputClassName ?? ''}`}
          autoComplete="off"
        />
        {directoryEnabled && (
          <div className="absolute right-3 top-0 bottom-0 flex items-center pointer-events-none">
            <Loader2 className={`h-4 w-4 text-gray-400 ${isSearching ? 'animate-spin' : 'hidden'}`} />
          </div>
        )}
      </div>

      {dropdownOpen && directoryEnabled && query.trim().length >= 2 && (
        <div
          ref={dropdownRef}
          className="absolute z-[60] w-full mt-1 max-h-[220px] overflow-y-auto rounded-md border border-gray-700 bg-gray-900 shadow-lg"
        >
          {isSearching ? (
            <div className="flex items-center justify-center py-4 text-sm text-gray-400">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Searching&hellip;
            </div>
          ) : searchError ? (
            <div className="px-3 py-4 text-sm text-amber-400 text-center">
              {searchError}
            </div>
          ) : results.length === 0 ? (
            <div className="px-3 py-4 text-sm text-gray-400 text-center">
              No users found
            </div>
          ) : (
            results.map((u) => (
              <button
                key={u.user_id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(u)}
                className="w-full flex flex-col px-3 py-2 text-left hover:bg-white/10 transition-colors cursor-pointer"
              >
                <span className="text-sm text-gray-100">{u.display_name}</span>
                <span className="text-xs text-gray-400">
                  {u.username}{u.email ? ` \u00b7 ${u.email}` : ''}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
