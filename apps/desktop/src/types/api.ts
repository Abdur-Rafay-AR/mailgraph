/**
 * TypeScript API contracts matching MailGraph backend models.
 */

export interface Account {
  id: number;
  provider: 'synthetic' | 'mbox' | 'imap' | 'gmail';
  display_name: string;
  email_address: string;
  created_at: string;
  last_sync_at: string | null;
  status: string;
}

export interface OverviewStats {
  total_messages: number;
  unread_messages: number;
  total_bytes: number;
  earliest_date: string | null;
  latest_date: string | null;
  total_senders: number;
  total_domains: number;
  total_accounts: number;
  top_senders_by_count: {
    id: number;
    address: string;
    name: string;
    domain: string;
    message_count: number;
    total_bytes: number;
  }[];
  categories: {
    name: string;
    color: string;
    count: number;
  }[];
  recent_sync: {
    status: string;
    started_at: string | null;
    completed_at: string | null;
    inserted_count: number;
  } | null;
}

export interface Sender {
  id: number;
  normalized_address: string;
  display_name: string;
  domain: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  is_protected: boolean;
  message_count: number;
  total_bytes: number;
  unread_count: number;
  category: string;
}

export interface SenderDetail {
  id: number;
  normalized_address: string;
  display_name: string;
  domain: string;
  is_protected: boolean;
  notes: string | null;
  message_count: number;
  total_bytes: number;
  unread_count: number;
  recent_messages: {
    id: number;
    subject: string;
    received_at: string;
    size_bytes: number;
    is_read: boolean;
    is_starred: boolean;
  }[];
}

export interface MessageAddress {
  address: string;
  display_name: string;
  role: 'from' | 'to' | 'cc' | 'bcc' | 'reply_to';
}

export interface Attachment {
  id: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  content_hash: string | null;
  is_inline: boolean;
  content_available: boolean;
}

export interface MessageItem {
  id: number;
  account_id: number;
  provider_message_id: string;
  folder_id: number | null;
  thread_id: number | null;
  subject: string;
  sender_name: string;
  sender_address: string;
  sender_domain: string;
  received_at: string;
  is_read: boolean;
  is_starred: boolean;
  is_important: boolean;
  has_attachments: boolean;
  size_bytes: number;
  snippet: string;
  category: string;
  category_color: string;
}

export interface MessageDetail extends MessageItem {
  sent_at: string | null;
  addresses: MessageAddress[];
  attachments: Attachment[];
  sanitized_html: string;
  body_text: string;
  category_reason?: string;
}

export interface QueryCondition {
  field: string;
  op: string;
  value: any;
}

export interface QueryAST {
  version?: number;
  account_ids?: number[];
  all?: QueryCondition[];
  any?: QueryCondition[];
  none?: QueryCondition[];
  search_term?: string;
  exclude_protected?: boolean;
}

export interface SearchResult {
  total_count: number;
  page: number;
  page_size: number;
  items: MessageItem[];
  facets: {
    total_matched: number;
    total_bytes: number;
    categories: Record<string, number>;
  };
}

export interface GraphNodeData {
  id: string;
  label: string;
  node_type: 'hub' | 'domain' | 'sender' | 'thread';
  domain?: string;
  sender_id?: number;
  address?: string;
  display_name?: string;
  thread_id?: number;
  message_count?: number;
  sender_count?: number;
  total_bytes?: number;
  unread_count?: number;
  first_seen?: string;
  last_seen?: string;
  category?: string;
  color?: string;
  is_protected?: boolean;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  weight: number;
}

export interface GraphResponse {
  elements: {
    nodes: { data: GraphNodeData }[];
    edges: { data: GraphEdgeData }[];
  };
}

export interface CleanupPreview {
  operation_type: 'trash' | 'archive';
  account_id: number;
  target_count: number;
  affected_threads_count: number;
  total_size_bytes: number;
  protected_excluded_count: number;
  date_range_start: string | null;
  date_range_end: string | null;
  top_senders: {
    address: string;
    name: string;
    count: number;
    total_bytes: number;
  }[];
  samples: {
    id: number;
    subject: string;
    sender_name: string;
    sender_address: string;
    received_at: string;
    size_bytes: number;
    category: string;
  }[];
  reversible: boolean;
  reversibility_note: string;
}

export interface CleanupOperation {
  id: number;
  account_id: number;
  operation_type: string;
  target_count: number;
  completed_count: number;
  failed_count: number;
  status: string;
  created_at: string;
  completed_at: string | null;
  undo_status: string | null;
}

export interface Insight {
  id: number;
  account_id: number | null;
  insight_type: string;
  title: string;
  description: string;
  evidence: Record<string, any>;
  confidence: number;
  created_at: string;
}

export interface AppSettings {
  app_name: string;
  app_version: string;
  data_dir: string;
  db_path: string;
  telemetry: boolean;
  index_message_bodies: boolean;
  download_attachments_automatically: boolean;
  local_ai_enabled: boolean;
  local_ai_endpoint: string;
  local_ai_model: string;
  default_delete_mode: string;
}

export interface ProtectionRule {
  id: number;
  account_id: number | null;
  rule_type: string;
  rule_value: string;
  reason: string | null;
  created_at: string;
  enabled: boolean;
}

export interface DuplicateAttachmentGroup {
  content_hash: string;
  filename: string;
  file_size: number;
  duplicate_count: number;
  total_bytes_occupied: number;
  references: {
    attachment_id: number;
    message_id: number;
    filename: string;
    message_subject: string;
    received_at: string;
    sender_address: string;
  }[];
}
