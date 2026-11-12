import React, { useState, useEffect, useMemo } from 'react';
import {
  Users,
  Search,
  Shield,
  ShieldAlert,
  Archive,
  Trash2,
  CheckSquare,
  Square,
  ArrowUpDown,
  Filter,
  ExternalLink,
  Info
} from 'lucide-react';
import { api } from '../../api/client';
import { Sender, SenderDetail } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';
import { Modal } from '../../components/Modal';

interface SendersViewProps {
  onOpenCleanupWithSenders?: (senderAddresses: string[], op: 'trash' | 'archive') => void;
  onOpenMessagesWithSender?: (senderAddress: string) => void;
}

export const SendersView: React.FC<SendersViewProps> = ({
  onOpenCleanupWithSenders,
  onOpenMessagesWithSender,
}) => {
  const [senders, setSenders] = useState<Sender[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('message_count');
  const [sortDir, setSortDir] = useState<string>('DESC');
  const [selectedSenderIds, setSelectedSenderIds] = useState<Set<number>>(new Set());
  
  // Sender detail modal
  const [activeSenderId, setActiveSenderId] = useState<number | null>(null);
  const [senderDetail, setSenderDetail] = useState<SenderDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  // Bulk cleanup preview modal state
  const [cleanupModalOpen, setCleanupModalOpen] = useState<boolean>(false);
  const [cleanupOperation, setCleanupOperation] = useState<'trash' | 'archive'>('trash');
  const [bulkPreview, setBulkPreview] = useState<any>(null);
  const [executingCleanup, setExecutingCleanup] = useState<boolean>(false);
  const [cleanupSuccessMsg, setCleanupSuccessMsg] = useState<string | null>(null);

  const fetchSenders = async () => {
    setLoading(true);
    try {
      const res = await api.getSenders({
        search,
        sort_by: sortBy,
        sort_dir: sortDir,
        page: 1,
        page_size: 100,
      });
      setSenders(res.items);
      setTotalCount(res.total_count);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSenders();
  }, [search, sortBy, sortDir]);

  // Load individual sender detail
  const handleOpenDetail = async (senderId: number) => {
    setActiveSenderId(senderId);
    setLoadingDetail(true);
    try {
      const detail = await api.getSenderDetail(senderId);
      setSenderDetail(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Toggle protection for a sender
  const handleToggleProtect = async (sender: Sender, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const nextState = !sender.is_protected;
      await api.setSenderProtection(sender.id, nextState);
      setSenders((prev) =>
        prev.map((s) => (s.id === sender.id ? { ...s, is_protected: nextState } : s))
      );
      if (senderDetail && senderDetail.id === sender.id) {
        setSenderDetail({ ...senderDetail, is_protected: nextState });
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Selection handlers
  const handleSelectAll = () => {
    if (selectedSenderIds.size === senders.length) {
      setSelectedSenderIds(new Set());
    } else {
      setSelectedSenderIds(new Set(senders.map((s) => s.id)));
    }
  };

  const handleToggleSelect = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(selectedSenderIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedSenderIds(next);
  };

  // Calculate stats for selected senders
  const selectedStats = useMemo(() => {
    const selected = senders.filter((s) => selectedSenderIds.has(s.id));
    const totalMsgs = selected.reduce((acc, s) => acc + s.message_count, 0);
    const totalBytes = selected.reduce((acc, s) => acc + s.total_bytes, 0);
    const protectedCount = selected.filter((s) => s.is_protected).length;
    return {
      count: selected.length,
      totalMsgs,
      totalMb: (totalBytes / (1024 * 1024)).toFixed(2),
      protectedCount,
    };
  }, [senders, selectedSenderIds]);

  // Initiate bulk cleanup preview
  const handleInitiateBulkCleanup = async (op: 'trash' | 'archive') => {
    if (selectedSenderIds.size === 0) return;
    setCleanupOperation(op);
    setExecutingCleanup(false);
    setCleanupSuccessMsg(null);
    setCleanupModalOpen(true);
    try {
      const preview = await api.previewBulkSendersCleanup({
        sender_ids: Array.from(selectedSenderIds),
        operation_type: op,
        exclude_protected: true,
      });
      setBulkPreview(preview);
    } catch (err: any) {
      console.error(err);
      alert(err.message || 'Failed to calculate cleanup preview');
    }
  };

  // Execute confirmed bulk cleanup
  const handleExecuteConfirmedBulkCleanup = async () => {
    if (selectedSenderIds.size === 0) return;
    setExecutingCleanup(true);
    try {
      const res = await api.executeBulkSendersCleanup({
        sender_ids: Array.from(selectedSenderIds),
        operation_type: cleanupOperation,
        exclude_protected: true,
      });
      setCleanupSuccessMsg(`Successfully executed ${cleanupOperation} on selected senders! (Op ID #${res.operation_id})`);
      setSelectedSenderIds(new Set());
      await fetchSenders();
    } catch (err: any) {
      alert(err.message || 'Execution error');
    } finally {
      setExecutingCleanup(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden">
      {/* Top Filter and Search Bar */}
      <div className="p-4 bg-bg-surface border-b border-border-subtle flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search senders by name, email address, or domain..."
              className="w-full pl-9 pr-3 py-1.5 bg-bg-deep border border-border-muted rounded text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-light"
            />
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {totalCount} senders discovered
          </span>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-bg-deep border border-border-muted rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
          >
            <option value="message_count">Message Volume (High to Low)</option>
            <option value="total_bytes">Storage Footprint (Largest)</option>
            <option value="unread_count">Unread Count</option>
            <option value="last_seen_at">Most Recent Activity</option>
            <option value="normalized_address">Alphabetical (Email)</option>
          </select>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => setSortDir(sortDir === 'DESC' ? 'ASC' : 'DESC')}
            title="Toggle sort direction"
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Floating Bulk Action Bar when senders are selected */}
      {selectedSenderIds.size > 0 && (
        <div className="bg-bg-elevated border-b border-brand/40 px-6 py-2.5 flex items-center justify-between animate-fadeIn z-10 shadow-lg">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono font-semibold text-brand-light">
              {selectedStats.count} senders selected
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({selectedStats.totalMsgs.toLocaleString()} messages, ~{selectedStats.totalMb} MB)
            </span>
            {selectedStats.protectedCount > 0 && (
              <span className="flex items-center gap-1 text-[11px] font-mono text-amber-400 bg-amber-950/40 border border-amber-800/60 px-2 py-0.5 rounded">
                <Shield className="w-3 h-3" />
                {selectedStats.protectedCount} protected (will be excluded from deletion)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="xs"
              variant="outline"
              onClick={() => setSelectedSenderIds(new Set())}
            >
              Deselect All
            </Button>
            <Button
              size="xs"
              variant="secondary"
              icon={<Archive className="w-3.5 h-3.5 text-blue-400" />}
              onClick={() => handleInitiateBulkCleanup('archive')}
            >
              Bulk Archive
            </Button>
            <Button
              size="xs"
              variant="danger"
              icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
              onClick={() => handleInitiateBulkCleanup('trash')}
            >
              Bulk Move to Trash
            </Button>
          </div>
        </div>
      )}

      {/* Main Sender Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-bg-surface border-b border-border-subtle text-[11px] font-mono uppercase tracking-wider text-slate-400 sticky top-0 z-10">
              <th className="py-2.5 px-4 w-10">
                <button
                  onClick={handleSelectAll}
                  className="text-slate-400 hover:text-slate-200"
                  title="Select all on this page"
                >
                  {selectedSenderIds.size > 0 && selectedSenderIds.size === senders.length ? (
                    <CheckSquare className="w-4 h-4 text-brand-light" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                </button>
              </th>
              <th className="py-2.5 px-3">Sender & Domain</th>
              <th className="py-2.5 px-3">Category</th>
              <th className="py-2.5 px-3 text-right">Messages</th>
              <th className="py-2.5 px-3 text-right">Storage</th>
              <th className="py-2.5 px-3 text-right">Unread</th>
              <th className="py-2.5 px-3 text-center">Protection</th>
              <th className="py-2.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle text-xs font-mono">
            {loading ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-400 font-sans">
                  Loading senders...
                </td>
              </tr>
            ) : senders.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-400 font-sans">
                  No senders found matching query. Try adjusting search filters or load demo data.
                </td>
              </tr>
            ) : (
              senders.map((s) => {
                const isSelected = selectedSenderIds.has(s.id);
                const sizeKb = (s.total_bytes / 1024).toFixed(0);
                const sizeMb = (s.total_bytes / (1024 * 1024)).toFixed(1);
                const displaySize = s.total_bytes > 1024 * 1024 ? `${sizeMb} MB` : `${sizeKb} KB`;

                return (
                  <tr
                    key={s.id}
                    onClick={() => handleOpenDetail(s.id)}
                    className={`table-row-hover ${
                      isSelected ? 'bg-brand/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-4" onClick={(e) => handleToggleSelect(s.id, e)}>
                      <button className="text-slate-400 hover:text-slate-200">
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-brand-light" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>

                    <td className="py-2.5 px-3 font-sans">
                      <div className="font-medium text-slate-200 truncate max-w-xs">
                        {s.display_name}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 truncate">
                        {s.normalized_address}
                      </div>
                    </td>

                    <td className="py-2.5 px-3">
                      <Badge label={s.category} />
                    </td>

                    <td className="py-2.5 px-3 text-right font-semibold text-slate-200">
                      {s.message_count.toLocaleString()}
                    </td>

                    <td className="py-2.5 px-3 text-right text-slate-400">
                      {displaySize}
                    </td>

                    <td className="py-2.5 px-3 text-right">
                      {s.unread_count > 0 ? (
                        <span className="text-amber-400 font-semibold">{s.unread_count}</span>
                      ) : (
                        <span className="text-slate-500">0</span>
                      )}
                    </td>

                    <td className="py-2.5 px-3 text-center" onClick={(e) => handleToggleProtect(s, e)}>
                      <button
                        title={s.is_protected ? 'Protected sender (click to unprotect)' : 'Click to protect sender'}
                        className={`p-1 rounded transition-colors ${
                          s.is_protected
                            ? 'text-emerald-400 hover:bg-emerald-950/40'
                            : 'text-slate-600 hover:text-slate-400 hover:bg-bg-elevated'
                        }`}
                      >
                        <Shield className={`w-4 h-4 ${s.is_protected ? 'fill-emerald-400/20' : ''}`} />
                      </button>
                    </td>

                    <td className="py-2.5 px-4 text-right space-x-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => {
                          setSelectedSenderIds(new Set([s.id]));
                          handleInitiateBulkCleanup('trash');
                        }}
                        title="Review messages and clean up"
                      >
                        Clean
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => {
                          if (onOpenMessagesWithSender) {
                            onOpenMessagesWithSender(s.normalized_address);
                          }
                        }}
                        title="View all messages in Message Explorer"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Sender Detail Drawer/Modal */}
      <Modal
        isOpen={activeSenderId !== null}
        onClose={() => {
          setActiveSenderId(null);
          setSenderDetail(null);
        }}
        title={senderDetail ? senderDetail.display_name : 'Sender Inspection'}
        subtitle={senderDetail ? senderDetail.normalized_address : ''}
        maxWidth="2xl"
      >
        {loadingDetail || !senderDetail ? (
          <div className="py-8 text-center text-slate-400 font-sans text-xs">
            Loading sender history...
          </div>
        ) : (
          <div className="space-y-4">
            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-slate-400 font-mono">Total Received</div>
                <div className="text-lg font-mono font-semibold text-slate-100">
                  {senderDetail.message_count.toLocaleString()}
                </div>
              </div>
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-slate-400 font-mono">Storage Footprint</div>
                <div className="text-lg font-mono font-semibold text-slate-100">
                  {(senderDetail.total_bytes / (1024 * 1024)).toFixed(2)} MB
                </div>
              </div>
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-slate-400 font-mono">Unread Backlog</div>
                <div className="text-lg font-mono font-semibold text-amber-400">
                  {senderDetail.unread_count}
                </div>
              </div>
            </div>

            {/* Protection Status Banner */}
            <div className="flex items-center justify-between p-3 rounded bg-bg-deep border border-border-subtle">
              <div className="flex items-center gap-2">
                <Shield className={`w-4 h-4 ${senderDetail.is_protected ? 'text-emerald-400' : 'text-slate-500'}`} />
                <div>
                  <div className="text-xs font-semibold text-slate-200">
                    {senderDetail.is_protected ? 'Sender is Protected' : 'Sender is Not Protected'}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {senderDetail.is_protected
                      ? 'Emails from this sender will be automatically shielded during bulk cleanup operations.'
                      : 'Can be cleaned up during bulk cleanup operations.'}
                  </div>
                </div>
              </div>
              <Button
                size="xs"
                variant={senderDetail.is_protected ? 'outline' : 'primary'}
                onClick={async () => {
                  const nextState = !senderDetail.is_protected;
                  await api.setSenderProtection(senderDetail.id, nextState);
                  setSenderDetail({ ...senderDetail, is_protected: nextState });
                  setSenders((prev) =>
                    prev.map((s) => (s.id === senderDetail.id ? { ...s, is_protected: nextState } : s))
                  );
                }}
              >
                {senderDetail.is_protected ? 'Unprotect' : 'Enable Protection'}
              </Button>
            </div>

            {/* Recent Messages Sample */}
            <div>
              <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
                Recent Messages from this sender
              </div>
              <div className="border border-border-subtle rounded divide-y divide-border-subtle max-h-60 overflow-y-auto">
                {senderDetail.recent_messages.map((m) => (
                  <div key={m.id} className="p-2.5 flex items-center justify-between text-xs hover:bg-bg-elevated">
                    <div className="truncate max-w-md font-sans">
                      <div className="text-slate-200 font-medium truncate">{m.subject}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{m.received_at}</div>
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 shrink-0">
                      {(m.size_bytes / 1024).toFixed(0)} KB
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Bar */}
            <div className="pt-3 border-t border-border-subtle flex justify-end gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (onOpenMessagesWithSender) {
                    onOpenMessagesWithSender(senderDetail.normalized_address);
                  }
                  setActiveSenderId(null);
                }}
              >
                Open in Messages Explorer
              </Button>
              <Button
                size="sm"
                variant="danger"
                icon={<Trash2 className="w-3.5 h-3.5" />}
                onClick={() => {
                  setSelectedSenderIds(new Set([senderDetail.id]));
                  setActiveSenderId(null);
                  handleInitiateBulkCleanup('trash');
                }}
              >
                Clean Up This Sender
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Bulk Cleanup Simulation & Confirmation Modal */}
      <Modal
        isOpen={cleanupModalOpen}
        onClose={() => setCleanupModalOpen(false)}
        title={`Confirm Bulk ${cleanupOperation === 'trash' ? 'Move to Trash' : 'Archive'}`}
        subtitle="Review exact target message counts, storage impact, and protected exclusions"
        maxWidth="2xl"
      >
        {cleanupSuccessMsg ? (
          <div className="py-6 text-center space-y-3">
            <div className="w-10 h-10 rounded-full bg-emerald-950/60 border border-emerald-600/60 text-emerald-400 mx-auto flex items-center justify-center">
              ✓
            </div>
            <div className="text-sm font-semibold text-slate-100">{cleanupSuccessMsg}</div>
            <p className="text-xs text-slate-400">
              The operation has been recorded in the local audit log. You can inspect or undo this action at any time in Cleanup Studio.
            </p>
            <Button size="sm" variant="primary" onClick={() => setCleanupModalOpen(false)}>
              Close
            </Button>
          </div>
        ) : !bulkPreview ? (
          <div className="py-8 text-center text-slate-400 font-sans text-xs">
            Calculating exact targets and protection exclusions...
          </div>
        ) : (
          <div className="space-y-4">
            {/* Impact Metric Cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-slate-400 font-mono">Affected Messages</div>
                <div className="text-xl font-mono font-bold text-slate-100">
                  {bulkPreview.target_count.toLocaleString()}
                </div>
              </div>
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-slate-400 font-mono">Storage Recovered</div>
                <div className="text-xl font-mono font-bold text-slate-100">
                  {(bulkPreview.total_size_bytes / (1024 * 1024)).toFixed(2)} MB
                </div>
              </div>
              <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                <div className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                  <Shield className="w-3 h-3" /> Protected Shielded
                </div>
                <div className="text-xl font-mono font-bold text-emerald-400">
                  {bulkPreview.protected_excluded_count}
                </div>
              </div>
            </div>

            {/* Reversibility Note */}
            <div className="p-3 rounded bg-blue-950/20 border border-blue-800/40 text-xs text-blue-200 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">{bulkPreview.reversibility_note}</span>
                <p className="text-[11px] text-blue-300/80 mt-0.5">
                  Target messages will be moved to the Trash on your live Gmail/IMAP account and updated locally. You can undo this action at any time from Cleanup Studio.
                </p>
              </div>
            </div>

            {/* Samples List */}
            {bulkPreview.samples && bulkPreview.samples.length > 0 && (
              <div>
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Sample of affected messages ({bulkPreview.samples.length} of {bulkPreview.target_count})
                </div>
                <div className="border border-border-subtle rounded divide-y divide-border-subtle max-h-40 overflow-y-auto">
                  {bulkPreview.samples.map((s: any) => (
                    <div key={s.id} className="p-2 flex items-center justify-between text-xs">
                      <div className="truncate max-w-md font-sans">
                        <span className="text-slate-300 font-medium">{s.subject}</span>
                        <span className="text-[11px] text-slate-500 font-mono ml-2">from {s.sender_address}</span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400 shrink-0">{s.received_at?.slice(0, 10)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action Confirmation Buttons */}
            <div className="pt-3 border-t border-border-subtle flex items-center justify-between">
              <Button size="sm" variant="ghost" onClick={() => setCleanupModalOpen(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                variant={cleanupOperation === 'trash' ? 'danger' : 'primary'}
                loading={executingCleanup}
                onClick={handleExecuteConfirmedBulkCleanup}
                icon={cleanupOperation === 'trash' ? <Trash2 className="w-3.5 h-3.5" /> : <Archive className="w-3.5 h-3.5" />}
              >
                Confirm: {cleanupOperation === 'trash' ? 'Move' : 'Archive'} {bulkPreview.target_count} Messages
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
