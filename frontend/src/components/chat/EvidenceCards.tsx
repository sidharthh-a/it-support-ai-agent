import React from 'react';
import { FileText, Database, Ticket, AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { useState } from 'react';
import { RagSource, SqlSource, TicketCreatedInfo } from '../../services/api';

const COLLAPSE_COUNT = 3;

export const RagSourcesCard: React.FC<{ sources: RagSource[] }> = ({ sources }) => {
  const [expanded, setExpanded] = useState(false);
  if (!sources?.length) return null;
  const visible = expanded ? sources : sources.slice(0, COLLAPSE_COUNT);

  return (
    <div className="rounded-2xl border border-emerald-200/70 bg-emerald-50/60 dark:border-emerald-500/20 dark:bg-emerald-500/5">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-xs font-semibold text-emerald-700 dark:text-emerald-300"
        aria-expanded={expanded}
      >
        <FileText className="h-4 w-4" />
        Knowledge Base Evidence ({sources.length})
        <span className="ml-auto">{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</span>
      </button>
      <div className="space-y-2 px-4 pb-3">
        {visible.map((s, i) => (
          <div key={i} className="rounded-xl border border-emerald-200/60 bg-white/70 p-3 dark:border-emerald-500/15 dark:bg-slate-900/50">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">{s.title}</p>
              {typeof s.score === 'number' && s.score > 0 && (
                <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                  {(s.score * 100).toFixed(0)}% match
                </span>
              )}
            </div>
            <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{s.snippet}</p>
          </div>
        ))}
        {sources.length > COLLAPSE_COUNT && (
          <button onClick={() => setExpanded((e) => !e)} className="text-xs font-medium text-emerald-600 hover:underline dark:text-emerald-400">
            {expanded ? 'Show less' : `Show ${sources.length - COLLAPSE_COUNT} more`}
          </button>
        )}
      </div>
    </div>
  );
};

export const SqlSourcesCard: React.FC<{ sources: SqlSource[] }> = ({ sources }) => {
  const [expanded, setExpanded] = useState(false);
  if (!sources?.length) return null;
  const isErrorLog = (s: SqlSource) => s.tool === 'search_error_logs';
  const ticketSources = sources.filter((s) => !isErrorLog(s));
  const logSources = sources.filter(isErrorLog);
  const visibleTickets = expanded ? ticketSources : ticketSources.slice(0, COLLAPSE_COUNT);

  return (
    <div className="space-y-2">
      {ticketSources.length > 0 && (
        <div className="rounded-2xl border border-sky-200/70 bg-sky-50/60 dark:border-sky-500/20 dark:bg-sky-500/5">
          <div className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-sky-700 dark:text-sky-300">
            <Database className="h-4 w-4" /> Historical Tickets (SQL)
          </div>
          <div className="space-y-1.5 px-4 pb-3">
            {visibleTickets.map((s, i) => (
              <pre key={i} className="max-h-36 overflow-y-auto whitespace-pre-wrap rounded-xl bg-white/70 p-2.5 font-mono text-[11px] leading-relaxed text-slate-600 dark:bg-slate-900/50 dark:text-slate-300">
                {s.result}
              </pre>
            ))}
            {ticketSources.length > COLLAPSE_COUNT && (
              <button onClick={() => setExpanded((e) => !e)} className="text-xs font-medium text-sky-600 hover:underline dark:text-sky-400">
                {expanded ? 'Show less' : `Show all ${ticketSources.length}`}
              </button>
            )}
          </div>
        </div>
      )}
      {logSources.length > 0 && (
        <div className="rounded-2xl border border-amber-200/70 bg-amber-50/60 dark:border-amber-500/20 dark:bg-amber-500/5">
          <div className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4" /> Error Logs (SQL)
          </div>
          <div className="space-y-1.5 px-4 pb-3">
            {logSources.map((s, i) => (
              <pre key={i} className="max-h-36 overflow-y-auto whitespace-pre-wrap rounded-xl bg-white/70 p-2.5 font-mono text-[11px] leading-relaxed text-slate-600 dark:bg-slate-900/50 dark:text-slate-300">
                {s.result}
              </pre>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const TicketCreatedCard: React.FC<{ ticket: TicketCreatedInfo; updated?: boolean }> = ({ ticket, updated }) => (
  <div className="flex items-center gap-3 rounded-2xl border border-violet-200/70 bg-violet-50/70 px-4 py-3 dark:border-violet-500/25 dark:bg-violet-500/10">
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 text-violet-600 dark:text-violet-300">
      <Ticket className="h-5 w-5" />
    </div>
    <div className="min-w-0 flex-1">
      <p className="text-xs font-bold text-violet-700 dark:text-violet-200">Support Ticket {updated ? 'Updated' : 'Created'}</p>
      <p className="truncate text-xs text-violet-600/80 dark:text-violet-300/70">
        #{ticket.ticket_number || ticket.ticket_id} · {ticket.title || ticket.message} · {ticket.priority || 'medium'} priority
      </p>
    </div>
    <span className="shrink-0 rounded-full bg-violet-500/15 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-violet-700 dark:text-violet-300">
      {ticket.status || 'open'}
    </span>
  </div>
);

export const ToolBadges: React.FC<{ tools: { tool_name: string; arguments: Record<string, unknown>; result_summary: string }[] }> = ({ tools }) => {
  const [expanded, setExpanded] = useState(false);
  if (!tools?.length) return null;
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 dark:border-slate-700/60 dark:bg-slate-800/40">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full flex-wrap items-center gap-1.5 px-3.5 py-2.5 text-left"
        aria-expanded={expanded}
      >
        <span className="mr-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
          Agent executed {tools.length} tool{tools.length > 1 ? 's' : ''}
        </span>
        {tools.map((t, i) => (
          <span key={i} className="rounded-md bg-brand-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-brand-600 dark:text-brand-300">
            {t.tool_name}
          </span>
        ))}
        <span className="ml-auto text-slate-400">{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</span>
      </button>
      {expanded && (
        <div className="space-y-2 border-t border-slate-200 px-3.5 py-3 dark:border-slate-700/60">
          {tools.map((t, i) => (
            <div key={i} className="rounded-xl bg-white p-2.5 dark:bg-slate-900/60">
              <p className="font-mono text-[11px] font-bold text-brand-600 dark:text-brand-300">{t.tool_name}</p>
              <p className="mt-0.5 truncate font-mono text-[10px] text-slate-400">{JSON.stringify(t.arguments)}</p>
              <p className="mt-1 line-clamp-3 text-[11px] text-slate-500 dark:text-slate-400">{t.result_summary}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
