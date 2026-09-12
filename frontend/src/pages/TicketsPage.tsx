import React, { useCallback, useEffect, useState } from 'react';
import {
  Plus, Filter, X, Clock, MessageSquare, AlertTriangle, ChevronRight, Loader2, Ticket as TicketIcon,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  api, SupportTicket, TicketComment, ErrorLogEntry, TicketUser, ApiError,
} from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Spinner } from '../components/ui/Spinner';

const STATUSES = ['open', 'in_progress', 'resolved', 'closed', 'escalated'] as const;
const PRIORITIES = ['low', 'medium', 'high', 'critical'] as const;
const CATEGORIES = ['network', 'hardware', 'software', 'access', 'security'] as const;

const STATUS_STYLE: Record<string, string> = {
  open: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  in_progress: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  resolved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  closed: 'bg-slate-100 text-slate-500 dark:bg-slate-500/15 dark:text-slate-400',
  escalated: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
};

const PRIORITY_STYLE: Record<string, string> = {
  low: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
  medium: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300',
  critical: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
};

const label = (s: string) => s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const TicketsPage: React.FC = () => {
  const { isStaff, user } = useAuth();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', priority: '', category: '', query: '' });
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [comments, setComments] = useState<TicketComment[]>([]);
  const [logs, setLogs] = useState<ErrorLogEntry[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [commentDraft, setCommentDraft] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [form, setForm] = useState({ title: '', description: '', priority: 'medium', category: 'software' });

  const loadTickets = useCallback(async () => {
    setLoading(true);
    try {
      setTickets(await api.getTickets({
        status: filters.status || undefined,
        priority: filters.priority || undefined,
        category: filters.category || undefined,
        query: filters.query || undefined,
      }));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const t = setTimeout(loadTickets, filters.query ? 250 : 0);
    return () => clearTimeout(t);
  }, [loadTickets, filters.query]);

  const openDetail = async (t: SupportTicket) => {
    setSelected(t);
    setDetailLoading(true);
    setError(null);
    try {
      const [c, l, fresh] = await Promise.all([api.getTicketComments(t.id), api.getTicketLogs(t.id), api.getTicket(t.id)]);
      setComments(c);
      setLogs(l);
      setSelected(fresh);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load ticket details');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleUpdate = async (patch: Parameters<typeof api.updateTicket>[1]) => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await api.updateTicket(selected.id, patch);
      setSelected(updated);
      await loadTickets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed');
    } finally {
      setBusy(false);
    }
  };

  const handleEscalate = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await api.escalateTicket(selected.id);
      setSelected(updated);
      await loadTickets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Escalation failed');
    } finally {
      setBusy(false);
    }
  };

  const handleComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !commentDraft.trim()) return;
    const created = await api.addTicketComment(selected.id, commentDraft.trim());
    setComments((prev) => [...prev, created]);
    setCommentDraft('');
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTicket(form);
      setCreateOpen(false);
      setForm({ title: '', description: '', priority: 'medium', category: 'software' });
      await loadTickets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Create failed');
    } finally {
      setBusy(false);
    }
  };

  const staffOrOwner = (t: SupportTicket) => isStaff || t.user_id === user?.id;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Support Tickets</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {isStaff ? 'All tickets across the workspace' : 'Your submitted tickets'}
            </p>
          </div>
          <button onClick={() => setCreateOpen(true)} className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-500/20 transition hover:bg-brand-500">
            <Plus className="h-4 w-4" /> New ticket
          </button>
        </div>

        {/* Filters */}
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" aria-label="Filter by status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
          <select value={filters.priority} onChange={(e) => setFilters((f) => ({ ...f, priority: e.target.value }))} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" aria-label="Filter by priority">
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
          </select>
          <select value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" aria-label="Filter by category">
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
          </select>
          <input
            value={filters.query}
            onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
            placeholder="Search title, description, #number…"
            className="min-w-[220px] flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          />
        </div>

        {/* Ticket table */}
        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : (
          <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700/60">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400 dark:bg-slate-800/60">
                <tr>
                  <th className="px-4 py-3 font-semibold">Ticket</th>
                  <th className="hidden px-4 py-3 font-semibold md:table-cell">Requester</th>
                  <th className="px-4 py-3 font-semibold">Priority</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="hidden px-4 py-3 font-semibold lg:table-cell">Updated</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900/40">
                {tickets.map((t) => (
                  <tr key={t.id} onClick={() => openDetail(t)} className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800 dark:text-slate-100">{t.title}</p>
                      <p className="text-[11px] text-slate-400">#{t.ticket_number} · {label(t.category)}</p>
                    </td>
                    <td className="hidden px-4 py-3 text-slate-500 dark:text-slate-400 md:table-cell">{t.creator?.full_name || `User ${t.user_id}`}</td>
                    <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${PRIORITY_STYLE[t.priority]}`}>{label(t.priority)}</span></td>
                    <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${STATUS_STYLE[t.status]}`}>{label(t.status)}</span></td>
                    <td className="hidden px-4 py-3 text-xs text-slate-400 lg:table-cell">{new Date(t.updated_at).toLocaleDateString()}</td>
                    <td className="px-2"><ChevronRight className="h-4 w-4 text-slate-300" /></td>
                  </tr>
                ))}
                {tickets.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-400">No tickets match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      <AnimatePresence>
        {selected && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 bg-slate-950/40" onClick={() => setSelected(null)} />
            <motion.aside
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 320 }}
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="border-b border-slate-200 p-5 dark:border-slate-800">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-400">#{selected.ticket_number}</p>
                    <h3 className="mt-0.5 text-lg font-bold leading-snug text-slate-900 dark:text-white">{selected.title}</h3>
                  </div>
                  <button onClick={() => setSelected(null)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close"><X className="h-5 w-5" /></button>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${STATUS_STYLE[selected.status]}`}>{label(selected.status)}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${PRIORITY_STYLE[selected.priority]}`}>{label(selected.priority)} priority</span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">{label(selected.category)}</span>
                </div>
                {/* Actions */}
                {staffOrOwner(selected) && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {isStaff && (
                      <select value="" onChange={(e) => e.target.value && handleUpdate({ status: e.target.value })} className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800" aria-label="Change status">
                        <option value="">Set status…</option>
                        {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                      </select>
                    )}
                    {isStaff && (
                      <select value="" onChange={(e) => e.target.value && handleUpdate({ priority: e.target.value })} className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800" aria-label="Change priority">
                        <option value="">Set priority…</option>
                        {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
                      </select>
                    )}
                    {isStaff && selected.status !== 'escalated' && (
                      <button onClick={handleEscalate} disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-500/20 disabled:opacity-50 dark:text-red-400">
                        <AlertTriangle className="h-3.5 w-3.5" /> Escalate
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-5">
                {error && <div className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">{error}</div>}
                {detailLoading ? (
                  <div className="flex justify-center py-10"><Spinner /></div>
                ) : (
                  <>
                    {/* Description */}
                    <section>
                      <h4 className="text-xs font-bold uppercase tracking-wide text-slate-400">Description</h4>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-600 dark:text-slate-300">{selected.description}</p>
                    </section>

                    {/* Timeline (audit history) */}
                    <section>
                      <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-400"><Clock className="h-3.5 w-3.5" /> Timeline</h4>
                      <ol className="mt-3 space-y-3 border-l border-slate-200 pl-4 dark:border-slate-700">
                        {(selected.history || []).map((h) => (
                          <li key={h.id} className="relative text-xs">
                            <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-brand-500 dark:border-slate-900" />
                            <p className="font-medium text-slate-700 dark:text-slate-200">
                              <strong>{h.field_changed}</strong> {h.old_value ? `: ${h.old_value} → ` : 'set to '}{h.new_value}
                            </p>
                            <p className="mt-0.5 text-[11px] text-slate-400">
                              {h.changed_by?.full_name || 'System'} · {new Date(h.timestamp).toLocaleString()}
                            </p>
                          </li>
                        ))}
                        {!selected.history?.length && <li className="text-xs text-slate-400">No changes recorded.</li>}
                      </ol>
                    </section>

                    {/* Related error logs */}
                    {logs.length > 0 && (
                      <section>
                        <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-400"><AlertTriangle className="h-3.5 w-3.5" /> Related error logs</h4>
                        <div className="mt-3 space-y-2">
                          {logs.map((l) => (
                            <div key={l.id} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                              <p className="font-mono text-[11px] font-bold text-amber-600 dark:text-amber-400">{l.error_code} · {l.service_name}</p>
                              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{l.log_message}</p>
                              <p className="mt-1 text-[10px] text-slate-400">{new Date(l.timestamp).toLocaleString()}</p>
                            </div>
                          ))}
                        </div>
                      </section>
                    )}

                    {/* Comments */}
                    <section>
                      <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-400"><MessageSquare className="h-3.5 w-3.5" /> Comments</h4>
                      <div className="mt-3 space-y-3">
                        {comments.map((c) => (
                          <div key={c.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700/60">
                            <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{c.author?.full_name || 'User'}</p>
                            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{c.body}</p>
                            <p className="mt-1 text-[10px] text-slate-400">{new Date(c.created_at).toLocaleString()}</p>
                          </div>
                        ))}
                        {!comments.length && <p className="text-xs text-slate-400">No comments yet.</p>}
                        <form onSubmit={handleComment} className="flex gap-2">
                          <input
                            value={commentDraft}
                            onChange={(e) => setCommentDraft(e.target.value)}
                            placeholder="Add a comment…"
                            className="flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                          />
                          <button type="submit" disabled={!commentDraft.trim()} className="rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50">Post</button>
                        </form>
                      </div>
                    </section>
                  </>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Create modal */}
      <AnimatePresence>
        {createOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onClick={() => setCreateOpen(false)}>
            <motion.form
              initial={{ scale: 0.95, y: 12 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              onSubmit={handleCreate}
              className="w-full max-w-lg space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-white"><TicketIcon className="h-5 w-5 text-brand-500" /> New support ticket</h3>
                <button type="button" onClick={() => setCreateOpen(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button>
              </div>
              <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required placeholder="Short title" className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100" />
              <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} required rows={4} placeholder="Describe the issue, error codes, affected device…" className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))} className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100" aria-label="Priority">
                  {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
                </select>
                <select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100" aria-label="Category">
                  {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                </select>
              </div>
              {error && <div className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">{error}</div>}
              <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-60">
                {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create ticket
              </button>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
