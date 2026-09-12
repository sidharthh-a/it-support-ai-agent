import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Square, Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import { api, ApiError } from '../services/api';
import { streamChat, DoneMeta } from '../services/stream';
import { useAuth } from '../context/AuthContext';
import { MessageBubble } from '../components/chat/MessageBubble';
import { ChatMessage } from '../components/chat/types';
import { ConversationsPanel } from '../components/chat/ConversationsPanel';

const SUGGESTIONS = [
  'How do I fix GlobalProtect VPN gateway timeout (ERR_VPN_AUTH_401)?',
  'Has this Wi-Fi certificate issue happened before?',
  'Create ticket: Locked out of Okta SSO account',
];

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hello! I'm your **grounded IT support assistant**. I search your knowledge base (RAG), ticket history and error logs before answering — and I never invent troubleshooting steps.\n\nAsk me about VPN, Wi-Fi, passwords, software issues, or ask me to create a ticket.",
};

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const ChatPage: React.FC = () => {
  const { conversationId: routeConvId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [statusLabel, setStatusLabel] = useState<string | null>(null);
  const [activeConvId, setActiveConvId] = useState<number | null>(routeConvId ? Number(routeConvId) : null);
  const [panelRefreshKey, setPanelRefreshKey] = useState(0);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  // Load conversation when route changes
  useEffect(() => {
    const id = routeConvId ? Number(routeConvId) : null;
    setActiveConvId(id);
    if (id === null) {
      setMessages([WELCOME]);
      return;
    }
    let cancelled = false;
    api
      .getConversation(id)
      .then((conv) => {
        if (cancelled) return;
        const loaded: ChatMessage[] = conv.messages.map((m) => ({ ...m, id: String(m.id) }));
        setMessages(loaded.length ? loaded : [WELCOME]);
      })
      .catch(() => {
        if (!cancelled) navigate('/chat', { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [routeConvId, navigate]);

  // Scroll preservation: only auto-scroll when user is already near the bottom.
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }, []);

  useEffect(() => {
    if (stickToBottomRef.current) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  const updateAssistantMessage = useCallback((msgId: string, updater: (prev: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === msgId ? updater(m) : m)));
  }, []);

  const runStream = useCallback(
    async (text: string, convId: number | null, historyMessages: ChatMessage[]) => {
      const userMsg: ChatMessage = { id: uid(), role: 'user', content: text, created_at: new Date().toISOString() };
      const assistantId = uid();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        tools_used: [],
        rag_sources: [],
        sql_sources: [],
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStreaming(true);
      setStatusLabel('Routing intent…');

      const controller = new AbortController();
      abortRef.current = controller;

      const chatHistory = historyMessages
        .filter((m) => m.id !== 'welcome' && m.content)
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));

      try {
        const done: DoneMeta | null = await streamChat(
          {
            message: text,
            conversationId: convId,
            history: chatHistory,
            signal: controller.signal,
          },
          {
            onStart: (cid) => {
              if (cid && cid !== activeConvId) {
                setActiveConvId(cid);
                setPanelRefreshKey((k) => k + 1);
                window.history.replaceState(null, '', `/chat/${cid}`);
              }
            },
            onStatus: (stage) => {
              setStatusLabel(
                stage === 'routing' ? 'Routing intent…' : stage === 'retrieving' ? 'Searching knowledge & logs…' : 'Synthesizing grounded answer…'
              );
            },
            onTool: (tool) => {
              updateAssistantMessage(assistantId, (prev) => ({
                ...prev,
                tools_used: [...(prev.tools_used || []), tool],
              }));
            },
            onTicket: (ticket) => {
              updateAssistantMessage(assistantId, (prev) => ({
                ...prev,
                ticket_created: ticket,
              }));
            },
            onToken: (delta) => {
              setStatusLabel(null);
              updateAssistantMessage(assistantId, (prev) => ({ ...prev, content: prev.content + delta }));
            },
            onDone: (meta) => {
              updateAssistantMessage(assistantId, () => ({
                ...assistantMsg,
                id: assistantId,
                role: 'assistant',
                content: meta.answer,
                created_at: new Date().toISOString(),
                tools_used: meta.tools_used,
                rag_sources: meta.rag_sources,
                sql_sources: meta.sql_sources,
                ticket_created: meta.ticket_created,
                ticket_updated: meta.ticket_updated,
                grounded: meta.grounded,
                confidence: meta.confidence,
                evidence_used: meta.evidence_used,
              }));
              setPanelRefreshKey((k) => k + 1);
            },
            onError: (detail) => {
              updateAssistantMessage(assistantId, (prev) => ({
                ...prev,
                content: prev.content || `⚠️ ${detail}`,
              }));
            },
          }
        );
        if (!done) {
          updateAssistantMessage(assistantId, (prev) => (prev.content ? prev : { ...prev, content: '⚠️ Generation stopped.' }));
        }
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === 'AbortError';
        updateAssistantMessage(assistantId, (prev) => ({
          ...prev,
          content: prev.content || (aborted ? '⏹ Generation cancelled.' : `⚠️ ${(err as Error).message}`),
        }));
        if (err instanceof ApiError && err.status === 401) {
          navigate('/login');
        }
      } finally {
        setStreaming(false);
        setStatusLabel(null);
        abortRef.current = null;
      }
    },
    [activeConvId, navigate, updateAssistantMessage]
  );

  const handleSend = useCallback(
    async (text?: string) => {
      const message = (text ?? input).trim();
      if (!message || streaming) return;
      setInput('');
      setLastUserMessage(message);
      await runStream(message, activeConvId, messages);
    },
    [input, streaming, activeConvId, messages, runStream]
  );

  const handleCancel = () => {
    abortRef.current?.abort();
  };

  // Retry: re-run the last user message, dropping the previous assistant reply.
  const handleRetry = useCallback(async () => {
    if (!lastUserMessage || streaming) return;
    setMessages((prev) => {
      const copy = [...prev];
      while (copy.length && copy[copy.length - 1].role === 'assistant') copy.pop();
      if (copy.length && copy[copy.length - 1].role === 'user') copy.pop();
      return copy;
    });
    await runStream(lastUserMessage, activeConvId, messages);
  }, [lastUserMessage, streaming, activeConvId, messages, runStream]);

  const handleNewChat = useCallback(() => {
    abortRef.current?.abort();
    setActiveConvId(null);
    setMessages([WELCOME]);
    setLastUserMessage(null);
    navigate('/chat');
  }, [navigate]);

  return (
    <div className="flex h-full min-h-0">
      {/* Conversations panel (desktop) */}
      <div className="hidden w-72 shrink-0 lg:block">
        <ConversationsPanel
          activeId={activeConvId}
          onSelect={(id) => navigate(`/chat/${id}`)}
          onNew={handleNewChat}
          refreshKey={panelRefreshKey}
        />
      </div>

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header strip */}
        <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-2.5 dark:border-slate-800">
          <ShieldCheck className="h-4 w-4 text-emerald-500" />
          <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">Grounded mode</span>
          <span className="text-xs text-slate-400">· pgvector RAG + SQL evidence only</span>
          {statusLabel && (
            <span className="ml-auto flex items-center gap-1.5 text-xs text-brand-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> {statusLabel}
            </span>
          )}
        </div>

        {/* Messages */}
        <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((m, idx) => (
              <MessageBubble
                key={m.id}
                message={m}
                streaming={streaming && idx === messages.length - 1 && m.role === 'assistant'}
                onRetry={!streaming && idx === messages.length - 1 ? handleRetry : undefined}
              />
            ))}
            {!streaming && messages.length <= 1 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 transition hover:border-brand-300 hover:text-brand-600 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:border-brand-500/40 dark:hover:text-brand-300"
                  >
                    <Sparkles className="h-3 w-3 text-amber-400" />
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-slate-200 p-4 dark:border-slate-800">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="mx-auto flex max-w-3xl items-end gap-2"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={1}
              placeholder={`Describe your IT issue, ${user?.full_name?.split(' ')[0] || 'there'}…`}
              disabled={streaming}
              className="max-h-40 min-h-[46px] flex-1 resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-500/15 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-500"
            />
            {streaming ? (
              <button
                type="button"
                onClick={handleCancel}
                className="flex h-[46px] items-center gap-2 rounded-2xl bg-red-500/10 px-4 text-sm font-semibold text-red-500 transition hover:bg-red-500/20"
                aria-label="Cancel generation"
              >
                <Square className="h-4 w-4" /> Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="flex h-[46px] items-center gap-2 rounded-2xl bg-brand-600 px-5 text-sm font-semibold text-white shadow-lg shadow-brand-500/20 transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
                <span className="hidden sm:inline">Send</span>
              </button>
            )}
          </form>
        </div>
      </div>

      {/* Conversations panel (mobile, below content) */}
      <div className="absolute inset-x-0 bottom-0 z-10 lg:hidden">{/* Simplified: mobile uses the drawer nav; history accessible on desktop */}</div>
    </div>
  );
};
