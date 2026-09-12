import React, { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Bot, User, Check, Copy, RefreshCw, RotateCcw } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { MessageBubbleProps } from './types';
import { RagSourcesCard, SqlSourcesCard, TicketCreatedCard, ToolBadges } from './EvidenceCards';

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch { /* clipboard unavailable */ }
      }}
      className="rounded-lg p-1.5 text-slate-400 opacity-0 transition hover:bg-slate-100 hover:text-slate-600 focus:opacity-100 group-hover:opacity-100 dark:hover:bg-slate-800"
      aria-label="Copy message"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

export const MessageBubble: React.FC<MessageBubbleProps> = memo(function MessageBubble({
  message,
  streaming = false,
  onRetry,
  onRegenerate,
}) {
  const isUser = message.role === 'user';
  const { theme } = useTheme();
  const hasEvidence =
    !isUser && ((message.rag_sources?.length ?? 0) > 0 || (message.sql_sources?.length ?? 0) > 0);

  return (
    <div className={`group flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${
          isUser
            ? 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            : 'bg-gradient-to-tr from-brand-600 to-indigo-500 text-white shadow-md shadow-brand-500/20'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={`flex min-w-0 max-w-[calc(100%-3rem)] flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Tool badges above the bubble */}
        {!isUser && message.tools_used && message.tools_used.length > 0 && (
          <div className="w-full max-w-2xl">
            <ToolBadges tools={message.tools_used} />
          </div>
        )}

        {/* Ticket card */}
        {!isUser && (message.ticket_created || message.ticket_updated) && (
          <div className="w-full max-w-2xl">
            <TicketCreatedCard ticket={(message.ticket_created || message.ticket_updated)!} updated={!message.ticket_created && !!message.ticket_updated} />
          </div>
        )}

        {/* Bubble */}
        <div
          className={`relative max-w-2xl rounded-2xl px-4 py-3 text-sm shadow-sm ${
            isUser
              ? 'rounded-tr-md bg-brand-600 text-white'
              : 'rounded-tl-md border border-slate-200 bg-white text-slate-800 dark:border-slate-700/70 dark:bg-slate-800/70 dark:text-slate-100'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const isBlock = match || String(children).includes('\n');
                    return isBlock ? (
                      <SyntaxHighlighter
        style={theme === 'dark' ? oneDark : oneLight}
                        language={match?.[1] || 'text'}
                        PreTag="div"
                        customStyle={{ borderRadius: '0.6rem', fontSize: '0.8rem', margin: 0 }}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {streaming && <span className="stream-caret ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 bg-brand-500" />}
            </div>
          )}
        </div>

        {/* Evidence below the bubble */}
        {hasEvidence && (
          <div className="w-full max-w-2xl space-y-2">
            {message.rag_sources && message.rag_sources.length > 0 && <RagSourcesCard sources={message.rag_sources} />}
            {message.sql_sources && message.sql_sources.length > 0 && <SqlSourcesCard sources={message.sql_sources} />}
          </div>
        )}

        {/* Meta row: timestamp + actions */}
        <div className={`flex items-center gap-1.5 px-1 ${isUser ? 'flex-row-reverse' : ''}`}>
          <span className="text-[10px] text-slate-400">
            {new Date(message.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && message.grounded !== null && message.grounded !== undefined && (
            <span
              className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                message.grounded
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                  : 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-400'
              }`}
            >
              {message.grounded ? 'grounded' : 'ungrounded'}
            </span>
          )}
          {!isUser && !streaming && message.content && <CopyButton text={message.content} />}
          {!isUser && !streaming && onRetry && (
            <button
              onClick={onRetry}
              className="rounded-lg p-1.5 text-slate-400 opacity-0 transition hover:bg-slate-100 hover:text-slate-600 focus:opacity-100 group-hover:opacity-100 dark:hover:bg-slate-800"
              aria-label="Regenerate response"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
});
