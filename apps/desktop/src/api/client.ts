import {
  Account,
  OverviewStats,
  Sender,
  SenderDetail,
  MessageDetail,
  SearchResult,
  QueryAST,
  GraphResponse,
  CleanupPreview,
  CleanupOperation,
  Insight,
  AppSettings,
  ProtectionRule,
  DuplicateAttachmentGroup,
} from '../types/api';

const API_BASE = 'http://127.0.0.1:28491/api';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      let errorMsg = `Server error ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorMsg = errJson.detail;
      } catch (_) {}
      throw new Error(errorMsg);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === 'TypeError' && err.message.includes('Failed to fetch')) {
      throw new Error('Local MailGraph backend service is offline. Please launch the backend server.');
    }
    throw err;
  }
}

export const api = {
  // Health & Overview
  getHealth: () => request<{ status: string; version: string }>('/health'),
  getOverview: () => request<OverviewStats>('/overview'),

  // Accounts
  getAccounts: () => request<Account[]>('/accounts'),
  createAccount: (data: { provider: string; display_name: string; email_address: string }) =>
    request<Account>('/accounts', { method: 'POST', body: JSON.stringify(data) }),
  deleteAccount: (id: number) => request<{ status: string }>(`/accounts/${id}`, { method: 'DELETE' }),
  generateSynthetic: (data: { display_name?: string; email_address?: string; message_count?: number; seed?: number }) =>
    request<{ status: string; account_id: number; inserted_count: number }>('/accounts/synthetic/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  importMbox: (accountId: number, filePath: string, limit?: number) =>
    request<{ status: string; inserted_count: number }>(`/accounts/mbox/import?account_id=${accountId}&file_path=${encodeURIComponent(filePath)}${limit ? `&limit=${limit}` : ''}`, {
      method: 'POST',
    }),

  // Senders
  getSenders: (params: {
    search?: string;
    domain?: string;
    category?: string;
    is_protected?: boolean;
    sort_by?: string;
    sort_dir?: string;
    page?: number;
    page_size?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.domain) q.set('domain', params.domain);
    if (params.category) q.set('category', params.category);
    if (params.is_protected !== undefined) q.set('is_protected', String(params.is_protected));
    if (params.sort_by) q.set('sort_by', params.sort_by);
    if (params.sort_dir) q.set('sort_dir', params.sort_dir);
    if (params.page) q.set('page', String(params.page));
    if (params.page_size) q.set('page_size', String(params.page_size));
    return request<{ total_count: number; page: number; page_size: number; items: Sender[] }>(`/senders?${q.toString()}`);
  },
  getSenderDetail: (id: number) => request<SenderDetail>(`/senders/${id}`),
  setSenderProtection: (id: number, is_protected: boolean) =>
    request<{ id: number; is_protected: boolean }>(`/senders/${id}/protect`, {
      method: 'POST',
      body: JSON.stringify({ is_protected }),
    }),
  previewBulkSendersCleanup: (data: { sender_ids: number[]; operation_type: 'trash' | 'archive'; exclude_protected?: boolean }) =>
    request<any>('/senders/bulk-cleanup-preview', { method: 'POST', body: JSON.stringify(data) }),
  executeBulkSendersCleanup: (data: { sender_ids: number[]; operation_type: 'trash' | 'archive'; exclude_protected?: boolean }) =>
    request<{ status: string; operation_id: number }>('/senders/bulk-cleanup-execute', { method: 'POST', body: JSON.stringify(data) }),

  // Messages
  searchMessages: (data: { query: QueryAST; page?: number; page_size?: number; sort_by?: string; sort_dir?: string }) =>
    request<SearchResult>('/messages/search', { method: 'POST', body: JSON.stringify(data) }),
  getMessageDetail: (id: number) => request<MessageDetail>(`/messages/${id}`),
  exportCsvUrl: () => `${API_BASE}/messages/export/csv`,

  // Graph
  getGraph: (params: {
    level?: 'domain' | 'sender' | 'thread';
    selected_domain?: string;
    selected_sender_id?: number;
    category?: string;
    start_date?: string;
    end_date?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.level) q.set('level', params.level);
    if (params.selected_domain) q.set('selected_domain', params.selected_domain);
    if (params.selected_sender_id) q.set('selected_sender_id', String(params.selected_sender_id));
    if (params.category) q.set('category', params.category);
    if (params.start_date) q.set('start_date', params.start_date);
    if (params.end_date) q.set('end_date', params.end_date);
    return request<GraphResponse>(`/graph?${q.toString()}`);
  },

  // Cleanup Studio
  calculateCleanupPreview: (data: { account_id?: number; operation_type: string; query: QueryAST }) =>
    request<CleanupPreview>('/cleanup/preview', { method: 'POST', body: JSON.stringify(data) }),
  executeCleanup: (data: { account_id?: number; operation_type: string; query: QueryAST }) =>
    request<CleanupOperation>('/cleanup/execute', { method: 'POST', body: JSON.stringify(data) }),
  undoCleanup: (operationId: number) =>
    request<{ operation_id: number; status: string; restored_count: number }>('/cleanup/undo', {
      method: 'POST',
      body: JSON.stringify({ operation_id: operationId }),
    }),
  listOperations: () => request<CleanupOperation[]>('/cleanup/operations'),

  // Timeline
  getTimelineVolume: (groupBy: 'year' | 'month' | 'day' = 'month') =>
    request<{ period: string; message_count: number; total_bytes: number; unread_count: number }[]>(`/timeline/volume?group_by=${groupBy}`),
  getTimelineSenders: (limit = 10) =>
    request<any[]>(`/timeline/senders?limit=${limit}`),

  // Attachments
  getAttachments: (params: { search?: string; mime_type?: string; min_size?: number; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.mime_type) q.set('mime_type', params.mime_type);
    if (params.min_size) q.set('min_size', String(params.min_size));
    if (params.page) q.set('page', String(params.page));
    if (params.page_size) q.set('page_size', String(params.page_size));
    return request<{ total_count: number; page: number; page_size: number; items: any[] }>(`/attachments?${q.toString()}`);
  },
  getDuplicateAttachments: () => request<{ duplicate_groups: DuplicateAttachmentGroup[] }>('/attachments/duplicates'),

  // Insights
  getInsights: () => request<Insight[]>('/insights'),
  dismissInsight: (id: number) => request<{ status: string }>(`/insights/${id}/dismiss`, { method: 'POST' }),

  // Settings & Protection
  getSettings: () => request<AppSettings>('/settings'),
  updateSettings: (data: Partial<AppSettings>) => request<AppSettings>('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getProtectionRules: () => request<ProtectionRule[]>('/settings/protection-rules'),
  createProtectionRule: (data: { rule_type: string; rule_value: string; reason?: string }) =>
    request<{ id: number; status: string }>('/settings/protection-rules', { method: 'POST', body: JSON.stringify(data) }),
  deleteProtectionRule: (id: number) => request<{ status: string }>(`/settings/protection-rules/${id}`, { method: 'DELETE' }),
  getAiStatus: () => request<{ is_available: boolean; status: string; endpoint: string; installed_models: string[]; active_model: string }>('/settings/ai/status'),
  translateNlQuery: (prompt: string) => request<QueryAST>('/settings/ai/query', { method: 'POST', body: JSON.stringify({ prompt }) }),
  wipeData: () => request<{ status: string; message: string }>('/settings/wipe-data', { method: 'POST' }),
};
