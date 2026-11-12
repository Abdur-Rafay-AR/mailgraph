import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Trash2,
  Archive,
  RotateCcw,
  AlertTriangle,
  Info,
  Calendar,
  Filter,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { api } from '../../api/client';
import { CleanupPreview, CleanupOperation, QueryAST, QueryCondition } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';
import { Modal } from '../../components/Modal';

interface CleanupStudioProps {
  initialQuery?: QueryAST;
}

export const CleanupStudio: React.FC<CleanupStudioProps> = ({ initialQuery }) => {
  const [activeTab, setActiveTab] = useState<'builder' | 'audit'>('builder');

  // Query Builder State
  const [operationType, setOperationType] = useState<'trash' | 'archive'>('trash');
  const [targetCategory, setTargetCategory] = useState<string>('newsletter');
  const [daysOld, setDaysOld] = useState<number>(90);
  const [readOnly, setReadOnly] = useState<boolean>(true);
  const [excludeProtected, setExcludeProtected] = useState<boolean>(true);
  const [customSearch, setCustomSearch] = useState<string>('');

  // Preview & Execution State
  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [calculatingPreview, setCalculatingPreview] = useState<boolean>(false);
  const [confirmModalOpen, setConfirmModalOpen] = useState<boolean>(false);
  const [executing, setExecuting] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<CleanupOperation | null>(null);

  // Audit Log State
  const [operations, setOperations] = useState<CleanupOperation[]>([]);
  const [loadingOps, setLoadingOps] = useState<boolean>(false);
  const [undoingId, setUndoingId] = useState<number | null>(null);

  // Initialize query if passed from other views
  useEffect(() => {
    if (initialQuery) {
      handleCalculatePreview(initialQuery);
    }
  }, [initialQuery]);

  const loadOperations = async () => {
    setLoadingOps(true);
    try {
      const data = await api.listOperations();
      setOperations(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingOps(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      loadOperations();
    }
  }, [activeTab]);

  const buildQueryAST = (): QueryAST => {
    const conditions: QueryCondition[] = [];
    if (targetCategory) {
      conditions.push({ field: 'category', op: 'eq', value: targetCategory });
    }
    if (daysOld > 0) {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - daysOld);
      conditions.push({ field: 'received_at', op: 'before', value: cutoff.toISOString() });
    }
    if (readOnly) {
      conditions.push({ field: 'is_read', op: 'eq', value: true });
    }

    return {
      version: 1,
      all: conditions,
      search_term: customSearch.trim() || undefined,
      exclude_protected: excludeProtected,
    };
  };

  const handleCalculatePreview = async (overrideAst?: QueryAST) => {
    const ast = overrideAst || buildQueryAST();
    setCalculatingPreview(true);
    setExecutionResult(null);
    try {
      const res = await api.calculateCleanupPreview({
        operation_type: operationType,
        query: ast,
      });
      setPreview(res);
    } catch (err: any) {
      alert(err.message || 'Failed to simulate cleanup preview');
    } finally {
      setCalculatingPreview(false);
    }
  };

  const handleExecuteOperation = async () => {
    if (!preview) return;
    setExecuting(true);
    try {
      const ast = buildQueryAST();
      const res = await api.executeCleanup({
        operation_type: operationType,
        query: ast,
      });
      setExecutionResult(res);
      setConfirmModalOpen(false);
      // Refresh operations in background
      loadOperations();
    } catch (err: any) {
      alert(err.message || 'Error executing operation');
    } finally {
      setExecuting(false);
    }
  };

  const handleUndo = async (operationId: number) => {
    setUndoingId(operationId);
    try {
      const res = await api.undoCleanup(operationId);
      alert(`Successfully restored ${res.restored_count} messages back to their original folders!`);
      await loadOperations();
    } catch (err: any) {
      alert(err.message || 'Error executing undo');
    } finally {
      setUndoingId(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden select-none">
      {/* Top Tabs */}
      <div className="px-6 py-3 bg-bg-surface border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-1 bg-bg-deep p-0.5 rounded border border-border-muted text-xs">
          <button
            onClick={() => setActiveTab('builder')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'builder' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Simulation & Cleanup Studio
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'audit' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Audit Trail & Undo Log
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2.5 py-1 rounded">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Protection Safeguards Active</span>
        </div>
      </div>

      {activeTab === 'builder' ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Query Formulation Card */}
          <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <Filter className="w-4 h-4 text-brand-light" />
              1. Formulate Cleanup Criteria
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              {/* Category */}
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">TARGET CATEGORY</label>
                <select
                  value={targetCategory}
                  onChange={(e) => setTargetCategory(e.target.value)}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value="newsletter">Newsletters & Subscriptions</option>
                  <option value="promotional">Promotions & Marketing</option>
                  <option value="notification">Automated System Notifications</option>
                  <option value="automated_report">Build / Cron Reports</option>
                  <option value="social">Social Media Alerts</option>
                  <option value="">Any Category</option>
                </select>
              </div>

              {/* Age Cutoff */}
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">AGE CUTOFF</label>
                <select
                  value={daysOld}
                  onChange={(e) => setDaysOld(Number(e.target.value))}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value={30}>Older than 30 days</option>
                  <option value={60}>Older than 60 days</option>
                  <option value={90}>Older than 90 days (3 months)</option>
                  <option value={180}>Older than 180 days (6 months)</option>
                  <option value={365}>Older than 1 year</option>
                  <option value={0}>Any age</option>
                </select>
              </div>

              {/* Destination Action */}
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">SAFE ACTION</label>
                <select
                  value={operationType}
                  onChange={(e) => setOperationType(e.target.value as 'trash' | 'archive')}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value="trash">Move to Trash (Recoverable)</option>
                  <option value="archive">Archive (Remove from Inbox)</option>
                </select>
              </div>
            </div>

            {/* Checkbox Options */}
            <div className="flex items-center gap-6 pt-2 text-xs">
              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={readOnly}
                  onChange={(e) => setReadOnly(e.target.checked)}
                  className="rounded bg-bg-deep border-border-muted text-brand focus:ring-0"
                />
                <span>Only include messages marked as Read</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-emerald-300">
                <input
                  type="checkbox"
                  checked={excludeProtected}
                  onChange={(e) => setExcludeProtected(e.target.checked)}
                  className="rounded bg-bg-deep border-border-muted text-brand focus:ring-0"
                />
                <span>Exclude protected senders and starred messages (Recommended)</span>
              </label>
            </div>

            {/* Calculate Button */}
            <div className="pt-2 flex justify-end">
              <Button
                variant="primary"
                size="sm"
                loading={calculatingPreview}
                onClick={() => handleCalculatePreview()}
              >
                Calculate Simulation Preview
              </Button>
            </div>
          </div>

          {/* Execution Result Banner */}
          {executionResult && (
            <div className="p-4 rounded-lg bg-emerald-950/40 border border-emerald-600/60 shadow-lg flex items-center justify-between animate-fadeIn text-xs">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <div className="font-semibold text-slate-100">
                    Operation #{executionResult.id} Completed Successfully
                  </div>
                  <div className="text-slate-300 text-[11px] font-mono mt-0.5">
                    {executionResult.completed_count} messages moved to {operationType}. Undo is available.
                  </div>
                </div>
              </div>
              <Button size="xs" variant="outline" onClick={() => handleUndo(executionResult.id)}>
                Undo This Action
              </Button>
            </div>
          )}

          {/* Simulation Preview Card */}
          {preview && (
            <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4 animate-fadeIn">
              <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  2. Simulation Results & Reversibility Assessment
                </h3>
                <span className="text-xs font-mono text-slate-400">
                  Calculated against local SQLite index
                </span>
              </div>

              {/* Metric Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                  <div className="text-[11px] text-slate-400 font-mono">TARGET MESSAGES</div>
                  <div className="text-xl font-bold font-mono text-slate-100">
                    {preview.target_count.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    across {preview.affected_threads_count} threads
                  </div>
                </div>

                <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                  <div className="text-[11px] text-slate-400 font-mono">ESTIMATED STORAGE</div>
                  <div className="text-xl font-bold font-mono text-slate-100">
                    {(preview.total_size_bytes / (1024 * 1024)).toFixed(2)} MB
                  </div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">
                    Reclaimable local storage
                  </div>
                </div>

                <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                  <div className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    PROTECTED EXCLUDED
                  </div>
                  <div className="text-xl font-bold font-mono text-emerald-400">
                    {preview.protected_excluded_count}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    Protected senders safe
                  </div>
                </div>

                <div className="p-3 bg-bg-deep rounded border border-border-subtle">
                  <div className="text-[11px] text-slate-400 font-mono">REVERSIBILITY</div>
                  <div className="text-sm font-semibold font-mono text-emerald-400 mt-1">
                    100% Recoverable
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    Logged in audit table
                  </div>
                </div>
              </div>

              {/* Top Impact Senders */}
              {preview.top_senders && preview.top_senders.length > 0 && (
                <div>
                  <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
                    Top Senders Represented in Target Set
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
                    {preview.top_senders.map((s) => (
                      <div key={s.address} className="p-2 rounded bg-bg-deep border border-border-subtle flex justify-between">
                        <span className="truncate pr-2 text-slate-300">{s.name || s.address}</span>
                        <span className="shrink-0 text-slate-400">{s.count} msgs ({(s.total_bytes / 1024).toFixed(0)} KB)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sample Target Messages */}
              {preview.samples && preview.samples.length > 0 && (
                <div>
                  <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
                    Representative Samples ({preview.samples.length} of {preview.target_count})
                  </div>
                  <div className="border border-border-subtle rounded divide-y divide-border-subtle max-h-48 overflow-y-auto text-xs">
                    {preview.samples.map((s) => (
                      <div key={s.id} className="p-2.5 flex items-center justify-between">
                        <div className="truncate max-w-lg font-sans">
                          <div className="text-slate-200 font-medium truncate">{s.subject}</div>
                          <div className="text-[11px] text-slate-500 font-mono">{s.sender_address} • {s.received_at?.slice(0, 10)}</div>
                        </div>
                        <Badge label={s.category} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Explicit Confirmation Trigger */}
              <div className="pt-3 border-t border-border-subtle flex items-center justify-between">
                <div className="text-xs text-slate-400">
                  Review complete. Ready to apply action?
                </div>
                <Button
                  size="md"
                  variant={operationType === 'trash' ? 'danger' : 'primary'}
                  disabled={preview.target_count === 0}
                  onClick={() => setConfirmModalOpen(true)}
                  icon={operationType === 'trash' ? <Trash2 className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
                >
                  Proceed to Confirmation ({preview.target_count} messages)
                </Button>
              </div>
            </div>
          )}

          {/* Modal for Explicit Confirmation */}
          <Modal
            isOpen={confirmModalOpen}
            onClose={() => setConfirmModalOpen(false)}
            title={`Explicit Confirmation: ${operationType === 'trash' ? 'Move to Trash' : 'Archive'}`}
            subtitle="Destructive safety requirement: verify your intent before mutating mailbox state"
            maxWidth="lg"
          >
            <div className="space-y-4 text-xs">
              <div className="p-3 rounded bg-amber-950/30 border border-amber-800/50 text-amber-200 flex items-start gap-2.5">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <p>
                  You are about to {operationType === 'trash' ? 'move' : 'archive'}{' '}
                  <strong className="text-white font-mono">{preview?.target_count} messages</strong> (~
                  {preview ? (preview.total_size_bytes / (1024 * 1024)).toFixed(2) : 0} MB).
                </p>
              </div>

              <p className="text-slate-300 leading-relaxed font-sans">
                MailGraph will sync this action with your live mailbox (moving messages to Trash on Gmail/IMAP) and snapshot the original state in local storage. You can undo this operation at any time from the Audit Trail tab.
              </p>

              <div className="p-3 bg-bg-deep rounded border border-border-subtle space-y-1 font-mono text-[11px]">
                <div className="text-slate-400">Target Query Summary:</div>
                <div className="text-slate-200">• Category: {targetCategory || 'Any'}</div>
                <div className="text-slate-200">• Age: Older than {daysOld} days</div>
                <div className="text-slate-200">• Protected Messages: Excluded ({preview?.protected_excluded_count} shielded)</div>
              </div>

              <div className="pt-3 border-t border-border-subtle flex justify-end gap-2">
                <Button size="sm" variant="ghost" onClick={() => setConfirmModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant={operationType === 'trash' ? 'danger' : 'primary'}
                  loading={executing}
                  onClick={handleExecuteOperation}
                >
                  Yes, {operationType === 'trash' ? 'Move' : 'Archive'} {preview?.target_count} Messages
                </Button>
              </div>
            </div>
          </Modal>
        </div>
      ) : (
        /* Audit Trail & Undo Log View */
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <Clock className="w-4 h-4 text-brand-light" />
              Local Operations Audit Log
            </h3>
            <Button size="xs" variant="ghost" onClick={loadOperations} loading={loadingOps}>
              Refresh Log
            </Button>
          </div>

          <div className="border border-border-subtle rounded divide-y divide-border-subtle bg-bg-surface text-xs font-mono">
            {loadingOps ? (
              <div className="py-8 text-center text-slate-400 font-sans">Loading audit records...</div>
            ) : operations.length === 0 ? (
              <div className="py-8 text-center text-slate-500 font-sans">
                No cleanup operations recorded yet.
              </div>
            ) : (
              operations.map((op) => {
                const canUndo = op.status === 'completed' && op.undo_status === 'available';
                return (
                  <div key={op.id} className="p-4 flex items-center justify-between hover:bg-bg-elevated transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-200">Operation #{op.id}</span>
                        <Badge label={op.operation_type.toUpperCase()} />
                        <span className="text-[11px] text-slate-400 font-mono">
                          {op.status === 'completed' ? (
                            <span className="text-emerald-400">Completed</span>
                          ) : op.status === 'undone' ? (
                            <span className="text-purple-400">Undone (Restored)</span>
                          ) : (
                            <span className="text-amber-400">{op.status}</span>
                          )}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        Executed: {op.created_at} • {op.completed_count} messages affected
                      </div>
                    </div>

                    <div>
                      {canUndo && (
                        <Button
                          size="xs"
                          variant="outline"
                          icon={<RotateCcw className="w-3.5 h-3.5 text-brand-light" />}
                          loading={undoingId === op.id}
                          onClick={() => handleUndo(op.id)}
                        >
                          Undo Operation
                        </Button>
                      )}
                      {op.status === 'undone' && (
                        <span className="text-xs text-slate-500 italic font-sans">Already restored</span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
