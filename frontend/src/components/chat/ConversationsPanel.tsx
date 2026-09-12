import React, { useEffect, useState } from 'react';
import { MessageSquarePlus, Search, MoreHorizontal, Pencil, Trash2, X, MessagesSquare } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { ConversationRead, api } from '../../services/api';

export const ConversationsPanel: React.FC<{
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  refreshKey: number;
}> = ({ activeId, onSelect, onNew, refreshKey }) => {
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const load = async (q?: string) => {
    setLoading(true);
    try {
      setConversations(await api.listConversations(q || undefined));
    } catch {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => load(search), search ? 250 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, refreshKey]);

  const handleRename = async (id: number) => {
    if (renameValue.trim()) {
      await api.renameConversation(id, renameValue.trim());
      load(search);
    }
    setRenaming(null);
  };

  const handleDelete = async (id: number) => {
    await api.deleteConversation(id);
    if (id === activeId) onNew();
    else load(search);
  };

  return (
    <div className="flex h-full flex-col border-r border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/30">
      <div className="space-y-2 p-3">
        <button
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition hover:bg-brand-500"
        >
          <MessageSquarePlus className="h-4 w-4" /> New chat
        </button>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-8 text-xs text-slate-800 placeholder-slate-400 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            aria-label="Search conversations"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" aria-label="Clear search">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {loading && <p className="px-3 py-4 text-xs text-slate-400">Loading…</p>}
        {!loading && conversations.length === 0 && (
          <div className="px-3 py-8 text-center">
            <MessagesSquare className="mx-auto h-8 w-8 text-slate-300 dark:text-slate-600" />
            <p className="mt-2 text-xs text-slate-400">{search ? 'No matches found.' : 'No conversations yet. Start a new chat!'}</p>
          </div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group relative flex items-center rounded-xl px-3 py-2.5 text-sm transition-colors ${
              c.id === activeId
                ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/60'
            }`}
          >
            {renaming === c.id ? (
              <input
                autoFocus
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={() => handleRename(c.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename(c.id);
                  if (e.key === 'Escape') setRenaming(null);
                }}
                className="w-full rounded-md border border-brand-300 bg-white px-2 py-1 text-xs outline-none dark:border-brand-500/40 dark:bg-slate-900"
              />
            ) : (
              <button onClick={() => onSelect(c.id)} className="min-w-0 flex-1 text-left">
                <p className="truncate text-[13px] font-medium">{c.title}</p>
                <p className="truncate text-[11px] text-slate-400">
                  {c.message_count > 0 ? `${c.message_count} messages` : 'Empty'} · {new Date(c.updated_at).toLocaleDateString()}
                </p>
              </button>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMenuFor(menuFor === c.id ? null : c.id);
              }}
              className="ml-1 rounded-md p-1 text-slate-400 opacity-0 hover:bg-slate-200 hover:text-slate-600 group-hover:opacity-100 dark:hover:bg-slate-700"
              aria-label={`Options for ${c.title}`}
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
            <AnimatePresence>
              {menuFor === c.id && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="absolute right-1 top-11 z-10 w-36 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-700 dark:bg-slate-800"
                  onMouseLeave={() => setMenuFor(null)}
                >
                  <button
                    onClick={() => {
                      setRenaming(c.id);
                      setRenameValue(c.title);
                      setMenuFor(null);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Rename
                  </button>
                  <button
                    onClick={() => {
                      setMenuFor(null);
                      handleDelete(c.id);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  );
};
