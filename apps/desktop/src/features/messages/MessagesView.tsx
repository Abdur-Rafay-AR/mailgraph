import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Paperclip,
  Star,
  Trash2,
  Archive,
  Download,
  ArrowUpDown,
  CheckSquare,
  Square,
  Shield,
  Clock,
  Tag,
  Undo2,
  CheckCircle2,
  X
} from 'lucide-react';
import { api } from '../../api/client';
import { MessageItem, QueryAST, QueryCondition, CleanupOperation } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';
import { MessageDetailModal } from './MessageDetailModal';
import { TagMessagesModal } from './TagMessagesModal';

interface MessagesViewProps {
  accountId?: number;
  initialSearch?: string;
  initialSender?: string;
  onClearSenderFilter?: () => void;
  onOpenCleanupWithQuery?: (ast: QueryAST) => void;
}

export const MessagesView: React.FC<MessagesViewProps> = ({
  accountId,
  initialSearch = '',
  initialSender = '',
  onClearSenderFilter,
  onOpenCleanupWithQuery,
}) => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Filters
  const [searchTerm, setSearchTerm] = useState<string>(initialSearch);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [unreadOnly, setUnreadOnly] = useState<boolean>(false);
  const [hasAttachmentsOnly, setHasAttachmentsOnly] = useState<boolean>(false);
  const [starredOnly, setStarredOnly] = useState<boolean>(false);
  const [excludeProtected, setExcludeProtected] = useState<boolean>(true);
  const [senderFilter, setSenderFilter] = useState<string>(initialSender);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setSenderFilter(initialSender);
    setPage(1);
  }, [initialSender]);
  
  // Sorting & Pagination
  const [sortBy, setSortBy] = useState<string>('received_at');
  const [sortDir, setSortDir] = useState<string>('DESC');
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;
  
  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  
  // Detail Modal
  const [activeMessageId, setActiveMessageId] = useState<number | null>(null);

  // Tag Modal & Toast
  const [isTagModalOpen, setIsTagModalOpen] = useState<boolean>(false);
  const [tagModalQuery, setTagModalQuery] = useState<QueryAST | null>(null);
  const [tagModalTargetCount, setTagModalTargetCount] = useState<number>(0);
  const [tagModalIsSelection, setTagModalIsSelection] = useState<boolean>(false);
  const [tagToast, setTagToast] = useState<{
    operationId: number;
    labelName: string;
    count: number;
    undoing: boolean;
    undone: boolean;
    restoredCount?: number;
  } | null>(null);

  const getCurrentSearchQuery = (): QueryAST => {
    const allConditions: QueryCondition[] = [];
    if (selectedCategory) {
      allConditions.push({ field: 'category', op: 'eq', value: selectedCategory });
    }
    if (unreadOnly) {
      allConditions.push({ field: 'is_read', op: 'eq', value: false });
    }
    if (hasAttachmentsOnly) {
      allConditions.push({ field: 'has_attachments', op: 'eq', value: true });
    }
    if (starredOnly) {
      allConditions.push({ field: 'is_starred', op: 'eq', value: true });
    }
    if (senderFilter) {
      allConditions.push({ field: 'sender_address', op: 'eq', value: senderFilter });
    }

    return {
      version: 1,
      account_ids: accountId !== undefined ? [accountId] : undefined,
      search_term: searchTerm.trim() || undefined,
      all: allConditions,
      exclude_protected: excludeProtected,
    };
  };

  const getSelectionQuery = (): QueryAST => {
    return {
      version: 1,
      account_ids: accountId !== undefined ? [accountId] : undefined,
      all: [{ field: 'id', op: 'in', value: Array.from(selectedIds) }],
      exclude_protected: excludeProtected,
    };
  };

  const handleOpenTagModal = () => {
    if (selectedIds.size > 0) {
      setTagModalQuery(getSelectionQuery());
      setTagModalTargetCount(selectedIds.size);
      setTagModalIsSelection(true);
    } else {
      setTagModalQuery(getCurrentSearchQuery());
      setTagModalTargetCount(totalCount);
      setTagModalIsSelection(false);
    }
    setIsTagModalOpen(true);
  };

  const handleTagSuccess = (operation: CleanupOperation, labelName: string) => {
    const count = operation.completed_count ?? operation.target_count ?? tagModalTargetCount;
    setSelectedIds(new Set());
    fetchMessages();
    setTagToast({
      operationId: operation.id,
      labelName,
      count,
      undoing: false,
      undone: false,
    });
  };

  const handleUndoTag = async (operationId: number) => {
    setTagToast((prev) => (prev ? { ...prev, undoing: true } : null));
    try {
      const res = await api.undoCleanup(operationId);
      setTagToast((prev) =>
        prev
          ? {
              ...prev,
              undoing: false,
              undone: true,
              restoredCount: res.restored_count,
            }
          : null
      );
      setSelectedIds(new Set());
      await fetchMessages();
    } catch (err: any) {
      setActionError(err.message || 'Error executing undo');
      setTagToast((prev) => (prev ? { ...prev, undoing: false } : null));
    }
  };

  const fetchMessages = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const ast = getCurrentSearchQuery();

      const res = await api.searchMessages({
        query: ast,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      setMessages(res.items);
      setTotalCount(res.total_count);
    } catch (err: any) {
      console.error(err);
      setActionError(err.message || 'Failed to search messages');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMessages();
  }, [searchTerm, selectedCategory, unreadOnly, hasAttachmentsOnly, starredOnly, excludeProtected, senderFilter, sortBy, sortDir, page, accountId]);

  // Handle Export CSV using the exact active search query
  const handleExportCsv = async () => {
    try {
      setActionError(null);
      const res = await fetch(api.exportCsvUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: getCurrentSearchQuery(),
        }),
      });
      if (!res.ok) {
        throw new Error(`Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mailgraph_export.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(err);
      setActionError(err.message || 'Failed to export CSV');
    }
  };

  // Selection helpers
  const handleToggleSelectAll = () => {
    if (selectedIds.size === messages.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(messages.map((m) => m.id)));
    }
  };

  const handleToggleSelect = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden">
      {/* Top Filter and Controls Bar */}
      <div className="p-4 bg-bg-surface border-b border-border-subtle space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              placeholder="Search subjects and message bodies with SQLite FTS5..."
              className="w-full pl-9 pr-3 py-1.5 bg-bg-deep border border-border-muted rounded text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-light"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-mono">
              {totalCount.toLocaleString()} matches
            </span>
            <Button
              size="xs"
              variant="outline"
              disabled={loading || (totalCount === 0 && selectedIds.size === 0)}
              icon={<Tag className="w-3.5 h-3.5 text-brand-light" />}
              onClick={handleOpenTagModal}
              title="Tag in Gmail"
            >
              Tag in Gmail
            </Button>
            <Button
              size="xs"
              variant="outline"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={handleExportCsv}
              title="Download CSV export"
            >
              Export CSV
            </Button>
          </div>
        </div>

        {/* Filter Badges and Toggle Row */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2 flex-wrap">
            {senderFilter && (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-brand/15 border border-brand/30 text-brand-light font-mono text-xs">
                Sender: {senderFilter}
                <button
                  onClick={() => {
                    setSenderFilter('');
                    setPage(1);
                    onClearSenderFilter?.();
                  }}
                  className="hover:text-white font-bold"
                  aria-label="Clear sender filter"
                >
                  ×
                </button>
              </span>
            )}

            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setPage(1);
              }}
              className="bg-bg-deep border border-border-muted rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Categories</option>
              <option value="finance">Finance & Banking</option>
              <option value="important">Important</option>
              <option value="personal">Personal</option>
              <option value="work">Work</option>
              <option value="newsletter">Newsletters</option>
              <option value="receipt_invoice">Receipts & Invoices</option>
              <option value="security">Security Alerts</option>
              <option value="promotional">Promotional</option>
              <option value="notification">Notifications</option>
              <option value="calendar">Calendar Events</option>
            </select>

            <button
              onClick={() => {
                setUnreadOnly(!unreadOnly);
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded border text-xs font-medium transition-colors ${
                unreadOnly
                  ? 'bg-amber-950/40 border-amber-600/60 text-amber-300'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              Unread Only
            </button>

            <button
              onClick={() => {
                setHasAttachmentsOnly(!hasAttachmentsOnly);
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded border text-xs font-medium flex items-center gap-1 transition-colors ${
                hasAttachmentsOnly
                  ? 'bg-blue-950/40 border-blue-600/60 text-blue-300'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <Paperclip className="w-3.5 h-3.5" />
              Attachments
            </button>

            <button
              onClick={() => {
                setStarredOnly(!starredOnly);
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded border text-xs font-medium flex items-center gap-1 transition-colors ${
                starredOnly
                  ? 'bg-yellow-950/40 border-yellow-600/60 text-yellow-300'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
              Starred
            </button>

            <button
              onClick={() => {
                setExcludeProtected(!excludeProtected);
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded border text-xs font-medium flex items-center gap-1 transition-colors ${
                excludeProtected
                  ? 'bg-emerald-950/40 border-emerald-600/60 text-emerald-300'
                  : 'bg-red-950/30 border-red-800 text-red-300'
              }`}
              title="When enabled, protected senders and starred messages are excluded from search/cleanup"
            >
              <Shield className="w-3.5 h-3.5" />
              {excludeProtected ? 'Protection Shield: ON' : 'Protection Shield: OFF'}
            </button>
          </div>

          {/* Sort Selection */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-bg-deep border border-border-muted rounded px-2 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="received_at">Received Date</option>
              <option value="size_bytes">Message Size</option>
              <option value="sender_address">Sender</option>
              <option value="subject">Subject</option>
            </select>
            <Button
              size="xs"
              variant="ghost"
              onClick={() => setSortDir(sortDir === 'DESC' ? 'ASC' : 'DESC')}
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {actionError && (
        <div className="px-4 py-2 bg-red-950/70 border-b border-red-700 text-red-200 text-xs font-mono flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-red-300 hover:text-white font-bold px-2">
            ×
          </button>
        </div>
      )}

      {/* Success / Undo Toast Banner */}
      {tagToast && (
        <div
          className={`px-4 py-2.5 border-b flex items-center justify-between text-xs transition-colors z-20 ${
            tagToast.undone
              ? 'bg-slate-900 border-border-subtle text-slate-300'
              : 'bg-brand/15 border-brand/40 text-brand-light shadow-inner'
          }`}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="font-mono">
              {tagToast.undone ? (
                <>
                  Successfully removed label <strong className="text-white">"{tagToast.labelName}"</strong> from{' '}
                  <strong className="text-white">{(tagToast.restoredCount ?? tagToast.count).toLocaleString()} messages</strong>.
                </>
              ) : tagToast.count === 0 ? (
                <span>Protected messages shielded: 0 messages labeled.</span>
              ) : (
                <>
                  Successfully applied label <strong className="text-white">"{tagToast.labelName}"</strong> to{' '}
                  <strong className="text-white">
                    {tagToast.count.toLocaleString()} message{tagToast.count === 1 ? '' : 's'}
                  </strong>{' '}
                  in Gmail.
                </>
              )}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {!tagToast.undone && (
              <Button
                size="xs"
                variant="outline"
                loading={tagToast.undoing}
                icon={<Undo2 className="w-3.5 h-3.5" />}
                onClick={() => handleUndoTag(tagToast.operationId)}
              >
                Undo
              </Button>
            )}
            <button
              onClick={() => setTagToast(null)}
              className="text-slate-400 hover:text-white p-1 transition-colors"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Floating Action Bar when messages are selected */}
      {selectedIds.size > 0 && (
        <div className="bg-bg-elevated border-b border-brand/40 px-6 py-2.5 flex items-center justify-between animate-fadeIn z-10 shadow-lg">
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="font-semibold text-brand-light">{selectedIds.size} messages selected</span>
          </div>

          <div className="flex items-center gap-2">
            <Button size="xs" variant="outline" onClick={() => setSelectedIds(new Set())}>
              Deselect All
            </Button>
            <Button
              size="xs"
              variant="secondary"
              icon={<Tag className="w-3.5 h-3.5 text-brand-light" />}
              onClick={handleOpenTagModal}
            >
              Tag in Gmail
            </Button>
            <Button
              size="xs"
              variant="secondary"
              icon={<Archive className="w-3.5 h-3.5 text-blue-400" />}
              onClick={() => {
                if (onOpenCleanupWithQuery) {
                  onOpenCleanupWithQuery({
                    all: [{ field: 'id', op: 'in', value: Array.from(selectedIds) }],
                    exclude_protected: excludeProtected,
                  });
                }
              }}
            >
              Archive Selected
            </Button>
            <Button
              size="xs"
              variant="danger"
              icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
              onClick={() => {
                if (onOpenCleanupWithQuery) {
                  onOpenCleanupWithQuery({
                    all: [{ field: 'id', op: 'in', value: Array.from(selectedIds) }],
                    exclude_protected: excludeProtected,
                  });
                }
              }}
            >
              Trash Selected
            </Button>
          </div>
        </div>
      )}

      {/* Message Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-bg-surface border-b border-border-subtle text-[11px] font-mono uppercase tracking-wider text-slate-400 sticky top-0 z-10">
              <th className="py-2.5 px-4 w-10">
                <button onClick={handleToggleSelectAll} className="text-slate-400 hover:text-slate-200">
                  {selectedIds.size > 0 && selectedIds.size === messages.length ? (
                    <CheckSquare className="w-4 h-4 text-brand-light" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                </button>
              </th>
              <th className="py-2.5 px-3 w-56">Sender</th>
              <th className="py-2.5 px-3">Subject & Preview</th>
              <th className="py-2.5 px-3 w-32">Category</th>
              <th className="py-2.5 px-3 w-28 text-right">Date</th>
              <th className="py-2.5 px-4 w-20 text-right">Size</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle text-xs">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-400 font-sans">
                  Querying local SQLite mailbox index...
                </td>
              </tr>
            ) : messages.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-400 font-sans">
                  No messages matched the query.
                </td>
              </tr>
            ) : (
              messages.map((m) => {
                const isSelected = selectedIds.has(m.id);
                return (
                  <tr
                    key={m.id}
                    onClick={() => setActiveMessageId(m.id)}
                    className={`table-row-hover ${isSelected ? 'bg-brand/10' : ''}`}
                  >
                    <td className="py-2.5 px-4" onClick={(e) => handleToggleSelect(m.id, e)}>
                      <button className="text-slate-400 hover:text-slate-200">
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-brand-light" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>

                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5 truncate">
                        {!m.is_read && <span className="w-1.5 h-1.5 rounded-full bg-brand-light shrink-0" />}
                        <span className={`truncate font-medium ${!m.is_read ? 'text-slate-100 font-semibold' : 'text-slate-300'}`}>
                          {m.sender_name || m.sender_address.split('@')[0]}
                        </span>
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 truncate">{m.sender_address}</div>
                    </td>

                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        {m.is_starred && <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400 shrink-0" />}
                        {m.has_attachments && <Paperclip className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                        <span className={`truncate ${!m.is_read ? 'text-slate-100 font-medium' : 'text-slate-300'}`}>
                          {m.subject || '(No Subject)'}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 truncate max-w-xl">{m.snippet}</div>
                    </td>

                    <td className="py-2.5 px-3">
                      <Badge label={m.category} color={m.category_color} />
                    </td>

                    <td className="py-2.5 px-3 text-right font-mono text-[11px] text-slate-400">
                      {m.received_at?.slice(0, 10)}
                    </td>

                    <td className="py-2.5 px-4 text-right font-mono text-[11px] text-slate-500">
                      {(m.size_bytes / 1024).toFixed(0)} KB
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalCount > pageSize && (
        <div className="px-4 py-2.5 bg-bg-surface border-t border-border-subtle flex items-center justify-between text-xs text-slate-400 font-mono">
          <div>
            Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, totalCount)} of {totalCount}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="xs"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span>Page {page} of {Math.ceil(totalCount / pageSize)}</span>
            <Button
              size="xs"
              variant="outline"
              disabled={page * pageSize >= totalCount}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Message Inspection Modal */}
      <MessageDetailModal
        messageId={activeMessageId}
        onClose={() => setActiveMessageId(null)}
        onArchive={async (id) => {
          if (onOpenCleanupWithQuery) {
            onOpenCleanupWithQuery({ all: [{ field: 'id', op: 'eq', value: id }] });
          }
          setActiveMessageId(null);
        }}
        onTrash={async (id) => {
          if (onOpenCleanupWithQuery) {
            onOpenCleanupWithQuery({ all: [{ field: 'id', op: 'eq', value: id }] });
          }
          setActiveMessageId(null);
        }}
      />

      {/* Tag in Gmail Modal */}
      <TagMessagesModal
        isOpen={isTagModalOpen}
        onClose={() => setIsTagModalOpen(false)}
        query={tagModalQuery}
        targetCount={tagModalTargetCount}
        isSelection={tagModalIsSelection}
        accountId={accountId}
        onSuccess={handleTagSuccess}
      />
    </div>
  );
};
