import type { QueryAST } from './api';

export * from './api';

export interface CategorySyncItem {
  category: string;
  label: string;
  count: number;
}

export interface CategorySyncPreview {
  account_id: number;
  total_messages: number;
  categories: CategorySyncItem[];
}

export interface CategorySyncExecuteResponse {
  batch_id: string;
  operation_ids: number[];
  labeled_count: number;
}

export interface CategorySyncUndoResponse {
  batch_id: string;
  undone_count: number;
  operation_ids: number[];
}

export interface CleanupPreviewParams {
  account_id?: number;
  operation_type: 'trash' | 'archive' | 'label';
  query: QueryAST;
  label_name?: string;
}

export interface CleanupExecuteParams {
  account_id?: number;
  operation_type: 'trash' | 'archive' | 'label';
  query: QueryAST;
  label_name?: string;
}
