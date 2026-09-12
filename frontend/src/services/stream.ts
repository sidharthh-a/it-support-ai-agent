import { API_BASE, authHeaders, ToolCallDetail, RagSource, SqlSource, TicketCreatedInfo } from './api';

export interface StreamHandlers {
  onStart?: (conversationId: number | null) => void;
  onStatus?: (stage: string) => void;
  onTool?: (tool: ToolCallDetail) => void;
  onTicket?: (ticket: TicketCreatedInfo) => void;
  onToken?: (delta: string) => void;
  onDone?: (meta: DoneMeta) => void;
  onError?: (detail: string) => void;
}

export interface DoneMeta {
  answer: string;
  grounded: boolean | null;
  confidence: number | null;
  evidence_used: string[];
  tools_used: ToolCallDetail[];
  rag_sources: RagSource[];
  sql_sources: SqlSource[];
  ticket_created: TicketCreatedInfo | null;
  ticket_updated: TicketCreatedInfo | null;
}

export interface StreamMessageOptions {
  message: string;
  conversationId?: number | null;
  history?: { role: string; content: string }[];
  signal?: AbortSignal;
}

/**
 * POST to the SSE chat/stream endpoint and dispatch events to handlers.
 * Returns the DoneMeta when the stream completes; throws on HTTP errors.
 */
export async function streamChat(options: StreamMessageOptions, handlers: StreamHandlers): Promise<DoneMeta | null> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      message: options.message,
      conversation_id: options.conversationId ?? null,
      conversation_history: options.history || [],
    }),
    signal: options.signal,
  });

  if (!res.ok) {
    let detail = `Stream failed (HTTP ${res.status})`;
    try {
      const parsed = await res.json();
      if (parsed?.detail) detail = parsed.detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('Streaming not supported by this browser');

  const decoder = new TextDecoder();
  let buffer = '';
  let doneMeta: DoneMeta | null = null;

  const dispatch = (eventName: string, dataJson: string) => {
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(dataJson);
    } catch {
      return;
    }
    switch (eventName) {
      case 'start':
        handlers.onStart?.((data.conversation_id as number | null) ?? null);
        break;
      case 'status':
        handlers.onStatus?.(data.stage as string);
        break;
      case 'tool':
        handlers.onTool?.(data as unknown as ToolCallDetail);
        break;
      case 'ticket':
        handlers.onTicket?.(data as unknown as TicketCreatedInfo);
        break;
      case 'token':
        handlers.onToken?.(data.delta as string);
        break;
      case 'done':
        doneMeta = data as unknown as DoneMeta;
        handlers.onDone?.(doneMeta);
        break;
      case 'error':
        handlers.onError?.((data.detail as string) || 'Unknown stream error');
        break;
      default:
        break;
    }
  };

  // Parse the SSE byte stream: events are separated by blank lines.
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    // Events are separated by "\n\n"; handle partial frames by buffering.
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      let eventName = 'message';
      const dataLines: string[] = [];
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event: ')) eventName = line.slice(7).trim();
        else if (line.startsWith('data: ')) dataLines.push(line.slice(6));
        else if (line.startsWith('data:')) dataLines.push(line.slice(5));
      }
      if (dataLines.length) dispatch(eventName, dataLines.join('\n'));
    }
  }

  return doneMeta;
}
