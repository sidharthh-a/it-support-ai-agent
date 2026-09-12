export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------
const TOKEN_KEY = 'itsupport_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------
async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearToken();
    // Let AuthContext react to the session expiry on next navigation.
    throw new ApiError('Session expired. Please sign in again.', 401);
  }
  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = `HTTP Error ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) errorMessage = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      if (errorText) errorMessage = errorText;
    }
    throw new ApiError(errorMessage, response.status);
  }
  return response.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  return handleResponse<T>(res);
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: 'admin' | 'support' | 'employee';
  department: string;
  is_active: boolean;
  created_at: string;
}

export interface ConversationRead {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview?: string | null;
}

export interface MessageRead {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant';
  content: string;
  tools_used?: ToolCallDetail[] | null;
  rag_sources?: RagSource[] | null;
  sql_sources?: SqlSource[] | null;
  ticket_created?: TicketCreatedInfo | null;
  ticket_updated?: TicketCreatedInfo | null;
  grounded?: boolean | null;
  confidence?: number | null;
  evidence_used?: string[] | null;
  created_at: string;
}

export interface ToolCallDetail {
  tool_name: string;
  arguments: Record<string, unknown>;
  result_summary: string;
}

export interface RagSource {
  title: string;
  category: string;
  snippet: string;
  score?: number;
  search_type?: string;
}

export interface SqlSource {
  tool: string;
  result: string;
}

export interface TicketCreatedInfo {
  ticket_id?: number;
  ticket_number?: string;
  title?: string;
  status?: string;
  priority?: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------
export const api = {
  // --- Auth ---
  async login(email: string, password: string) {
    return request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async register(payload: { email: string; password: string; full_name: string; role?: string; department?: string }) {
    return request<UserProfile>('/auth/register', { method: 'POST', body: JSON.stringify(payload) });
  },

  async me() {
    return request<UserProfile>('/auth/me');
  },

  async changePassword(current_password: string, new_password: string) {
    return request<UserProfile>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    });
  },

  // --- Conversations ---
  async listConversations(search?: string) {
    const qs = search ? `?search=${encodeURIComponent(search)}` : '';
    return request<ConversationRead[]>(`/conversations/${qs}`);
  },

  async createConversation(title?: string) {
    return request<ConversationRead>('/conversations/', {
      method: 'POST',
      body: JSON.stringify({ title: title || 'New conversation' }),
    });
  },

  async renameConversation(id: number, title: string) {
    return request<ConversationRead>(`/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },

  async deleteConversation(id: number) {
    return request<void>(`/conversations/${id}`, { method: 'DELETE' });
  },

  async getConversation(id: number) {
    return request<ConversationRead & { messages: MessageRead[] }>(`/conversations/${id}`);
  },

  // --- Chat (sync fallback) ---
  async sendChatMessage(message: string, conversationId?: number | null, history: { role: string; content: string }[] = []) {
    return request<{
      answer: string;
      tools_used: ToolCallDetail[];
      ticket_created?: TicketCreatedInfo | null;
      ticket_updated?: TicketCreatedInfo | null;
      rag_sources?: RagSource[];
      sql_sources?: SqlSource[];
    }>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId ?? null, conversation_history: history }),
    });
  },

  // --- Tickets ---
  async getTickets(filters?: { query?: string; status?: string; priority?: string; category?: string; assigned_to_id?: number }) {
    const qp = new URLSearchParams();
    if (filters?.query) qp.append('query', filters.query);
    if (filters?.status) qp.append('status', filters.status);
    if (filters?.priority) qp.append('priority', filters.priority);
    if (filters?.category) qp.append('category', filters.category);
    if (filters?.assigned_to_id) qp.append('assigned_to_id', String(filters.assigned_to_id));
    const qs = qp.toString();
    return request<SupportTicket[]>(`/tickets/${qs ? `?${qs}` : ''}`);
  },

  async getTicket(id: number) {
    return request<SupportTicket>(`/tickets/${id}`);
  },

  async createTicket(data: { title: string; description: string; priority: string; category: string; device_id?: number }) {
    return request<SupportTicket>('/tickets/', { method: 'POST', body: JSON.stringify(data) });
  },

  async updateTicket(id: number, data: { status?: string; priority?: string; title?: string; description?: string; assigned_to_id?: number; category?: string }) {
    return request<SupportTicket>(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async escalateTicket(id: number) {
    return request<SupportTicket>(`/tickets/${id}/escalate`, { method: 'POST' });
  },

  async getTicketComments(id: number) {
    return request<TicketComment[]>(`/tickets/${id}/comments`);
  },

  async addTicketComment(id: number, body: string) {
    return request<TicketComment>(`/tickets/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) });
  },

  async getTicketLogs(id: number) {
    return request<ErrorLogEntry[]>(`/tickets/${id}/logs`);
  },

  // --- Knowledge ---
  async getKnowledgeDocs() {
    return request<KnowledgeDocument[]>('/knowledge/');
  },

  async searchKnowledge(query: string, limit = 5) {
    return request<SearchResult[]>(`/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  },

  async uploadKnowledgeDoc(data: { title: string; category: string; content: string; file_type?: string }) {
    return request<KnowledgeDocument>('/knowledge/', { method: 'POST', body: JSON.stringify(data) });
  },

  async uploadKnowledgeFile(title: string, category: string, file: File, sourceUrl?: string) {
    const formData = new FormData();
    formData.append('title', title);
    formData.append('category', category);
    formData.append('file', file);
    if (sourceUrl) formData.append('source_url', sourceUrl);
    return request<KnowledgeDocument>('/knowledge/upload', { method: 'POST', body: formData });
  },

  async deleteKnowledgeDoc(id: number) {
    return request<void>(`/knowledge/${id}`, { method: 'DELETE' });
  },

  async previewKnowledgeDoc(id: number) {
    return request<KnowledgePreview>(`/knowledge/${id}/preview`);
  },

  async reindexKnowledgeDoc(id: number) {
    return request<KnowledgeDocument>(`/knowledge/${id}/reindex`, { method: 'POST' });
  },

  // --- Analytics ---
  async getAnalytics() {
    return request<AnalyticsSummary>('/analytics/');
  },

  async getAnalyticsDashboard(days = 30) {
    return request<AnalyticsDashboard>(`/analytics/dashboard?days=${days}`);
  },

  // --- Admin ---
  async getSystemInfo() {
    return request<SystemInfo>('/admin/system');
  },

  async reindexAll() {
    return request<{ reindexed: number; skipped: number; dimension: number }>('/admin/reindex-all', { method: 'POST' });
  },

  async getAdminUsers() {
    return request<UserProfile[]>('/admin/users');
  },

  async createAdminUser(payload: { email: string; password: string; full_name: string; role: string; department?: string }) {
    return request<UserProfile>('/admin/users', { method: 'POST', body: JSON.stringify(payload) });
  },

  async updateAdminUser(id: number, payload: { full_name?: string; role?: string; department?: string; is_active?: boolean; password?: string }) {
    return request<UserProfile>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
  },

  async getAdminLogs() {
    return request<AdminLog[]>('/admin/logs');
  },

  // --- Misc (legacy pages kept working) ---
  async getIncidents() {
    return request<Incident[]>('/incidents/');
  },

  async getDevices(query?: string) {
    const url = query ? `/devices/?query=${encodeURIComponent(query)}` : '/devices/';
    return request<Device[]>(url);
  },
};

// ---------------------------------------------------------------------------
// Shared DTOs
// ---------------------------------------------------------------------------
export interface TicketUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  department: string;
}

export interface TicketHistory {
  id: number;
  ticket_id: number;
  changed_by_id?: number;
  field_changed: string;
  old_value?: string | null;
  new_value?: string | null;
  timestamp: string;
  changed_by?: TicketUser | null;
}

export interface Resolution {
  id: number;
  ticket_id: number;
  solution_summary: string;
  steps_taken: string;
  resolved_by_id: number;
  resolved_at: string;
  resolved_by?: TicketUser | null;
}

export interface TicketComment {
  id: number;
  ticket_id: number;
  author_id?: number | null;
  body: string;
  created_at: string;
  author?: TicketUser | null;
}

export interface ErrorLogEntry {
  id: number;
  device_id?: number | null;
  ticket_id?: number | null;
  service_name: string;
  error_code: string;
  log_message: string;
  stack_trace?: string | null;
  timestamp: string;
}

export interface SupportTicket {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed' | 'escalated';
  priority: 'low' | 'medium' | 'high' | 'critical';
  category: 'network' | 'hardware' | 'software' | 'access' | 'security';
  user_id: number;
  assigned_to_id?: number | null;
  device_id?: number | null;
  created_at: string;
  updated_at: string;
  creator?: TicketUser | null;
  assignee?: TicketUser | null;
  resolution?: Resolution | null;
  history?: TicketHistory[];
  comments?: TicketComment[];
}

export interface DocumentChunk {
  id: number;
  document_id: number;
  chunk_index: number;
  content: string;
  metadata_json?: Record<string, unknown>;
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  category: string;
  file_type: string;
  source_url?: string | null;
  created_at: string;
  updated_at: string;
  chunks: DocumentChunk[];
}

export interface KnowledgePreview {
  id: number;
  title: string;
  category: string;
  file_type: string;
  source_url?: string | null;
  created_at: string;
  chunk_count: number;
  content: string;
  truncated: boolean;
}

export interface SearchResult {
  document_id: number;
  chunk_id: number;
  title: string;
  category: string;
  content: string;
  score: number;
  search_type?: string;
}

export interface Incident {
  id: number;
  title: string;
  description: string;
  severity: 'P1' | 'P2' | 'P3' | 'P4';
  status: 'investigating' | 'identified' | 'monitoring' | 'resolved';
  ticket_id?: number | null;
  affected_service: string;
  started_at: string;
  resolved_at?: string | null;
}

export interface Device {
  id: number;
  user_id?: number;
  device_name: string;
  serial_number: string;
  os: string;
  status: string;
  ip_address?: string | null;
  created_at: string;
}

export interface AdminLog {
  id: number;
  service_name: string;
  error_code: string;
  log_message: string;
  timestamp: string;
}

export interface AnalyticsSummary {
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets: number;
  resolved_tickets: number;
  escalated_tickets: number;
  total_incidents: number;
  total_devices: number;
  total_knowledge_docs: number;
  tickets_by_status: { status: string; count: number }[];
  tickets_by_category: { category: string; count: number }[];
  tickets_by_priority: { priority: string; count: number }[];
  ai_resolution_rate: number;
}

export interface AnalyticsDashboard {
  summary: AnalyticsSummary;
  tickets_by_priority: { priority: string; count: number }[];
  tickets_by_category: { category: string; count: number }[];
  daily_trend: { date: string; count: number }[];
  avg_resolution_time_hours: number;
  top_recurring_errors: { error_code: string; count: number }[];
  knowledge_usage: {
    total_documents: number;
    total_chunks: number;
    embedded_chunks: number;
    embedding_coverage: number;
    documents_by_category: { category: string; count: number }[];
  };
  resolution_rate_by_category: { category: string; total: number; resolved: number; rate: number }[];
}

export interface SystemInfo {
  status: string;
  environment: string;
  version: string;
  python_version: string;
  platform: string;
  database: { healthy: boolean; latency_ms: number | null };
  embedding: {
    provider: string;
    model: string;
    dimension: number;
    documents: number;
    chunks: number;
    embedded_chunks: number;
    embedding_coverage: number;
  };
  llm: { gemini_model: string; gemini_configured: boolean };
  generated_at: string;
}
