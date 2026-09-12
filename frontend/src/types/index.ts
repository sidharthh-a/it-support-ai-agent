export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'user' | 'technician' | 'admin';
  department: string;
  created_at: string;
}

export interface Device {
  id: number;
  user_id?: number;
  device_name: string;
  serial_number: string;
  os: string;
  status: 'active' | 'maintenance' | 'retired';
  ip_address?: string;
  created_at: string;
  user?: User;
}

export interface TicketHistory {
  id: number;
  ticket_id: number;
  changed_by_id?: number;
  field_changed: string;
  old_value?: string;
  new_value?: string;
  timestamp: string;
  changed_by?: User;
}

export interface Resolution {
  id: number;
  ticket_id: number;
  solution_summary: string;
  steps_taken: string;
  resolved_by_id: number;
  resolved_at: string;
  resolved_by?: User;
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
  assigned_to_id?: number;
  device_id?: number;
  created_at: string;
  updated_at: string;
  creator?: User;
  assignee?: User;
  device?: Device;
  resolution?: Resolution;
  history?: TicketHistory[];
}

export interface Incident {
  id: number;
  title: string;
  description: string;
  severity: 'P1' | 'P2' | 'P3' | 'P4';
  status: 'investigating' | 'identified' | 'monitoring' | 'resolved';
  ticket_id?: number;
  affected_service: string;
  started_at: string;
  resolved_at?: string;
  ticket?: SupportTicket;
}

export interface DocumentChunk {
  id: number;
  document_id: number;
  chunk_index: number;
  content: string;
  metadata_json?: Record<string, any>;
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  category: string;
  file_type: string;
  source_url?: string;
  created_at: string;
  updated_at: string;
  chunks: DocumentChunk[];
}

export interface SearchResult {
  document_id: number;
  chunk_id: number;
  title: string;
  category: string;
  content: string;
  score: number;
}

export interface ToolCallDetail {
  tool_name: string;
  arguments: Record<string, any>;
  result_summary: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tools_used?: ToolCallDetail[];
  ticket_created?: any;
  ticket_updated?: any;
  rag_sources?: any[];
  sql_sources?: any[];
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
