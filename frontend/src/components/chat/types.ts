import { MessageRead } from '../../services/api';

export type ChatMessage = Partial<Omit<MessageRead, 'id' | 'created_at'>> & {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  conversation_id?: number;
  created_at?: string;
  pending?: boolean;
};

export interface MessageBubbleProps {
  message: ChatMessage;
  streaming?: boolean;
  onRetry?: () => void;
  onRegenerate?: () => void;
}
