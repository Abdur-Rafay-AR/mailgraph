import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Trash2,
  Archive,
  Tag,
  RotateCcw,
  AlertTriangle,
  Info,
  Calendar,
  Filter,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ArrowRight,
  RefreshCw
} from 'lucide-react';
import { api } from '../../api/client';
import { CleanupPreview, CleanupOperation, QueryAST, QueryCondition } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';
import { Modal } from '../../components/Modal';

const PRESET_LABELS = [
  'MailGraph/Finance',
  'MailGraph/Receipts',
  'MailGraph/Newsletters',
  'MailGraph/Security',
  'MailGraph/Personal',
  'MailGraph/Work',
  'MailGraph/Promotional',
];

interface CleanupStudioProps {
  accountId?: number;
  initialQuery?: QueryAST;
  onClearInitialQuery?: () => void;
  onOperationsChanged?: () => void;
}

export const CleanupStudio: React.FC<CleanupStudioProps> = ({
  accountId,
  initialQuery,
  onClearInitialQuery,
  onOperationsChanged,
}) => {
  const [activeTab, setActiveTab] = useState<'builder' | 'audit'>('builder');

  // Query Builder State
  const [operationType, setOperationType] = useState<'trash' | 'archive' | 'label'>('trash');
  const [labelName, setLabelName] = useState<string>('MailGraph/Finance');
  const [targetCategory, setTargetCategory] = useState<string>('newsletter');
  const [daysOld, setDaysOld] = useState<number>(90);
  const [readOnly, setReadOnly] = useState<boolean>(true);
  const [excludeProtected, setExcludeProtected] = useState<boolean>(true);
  const [customSearch, setCustomSearch] = useState<string>('');

  // Track the exact AST currently previewed so execution ALWAYS matches preview
  const [activeAst, setActiveAst] = useState<QueryAST | null>(null);
  const [isExternalQuery, setIsExternalQuery] = useState<boolean>(false);

  // Preview & Execution State
  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [calculatingPreview, setCalculatingPreview] = useState<boolean>(false);
  const [confirmModalOpen, setConfirmModalOpen] = useState<boolean>(false);
  const [executing, setExecuting] = useState<boolean>(false);
  const [execProgress, setExecProgress] = useState<number>(0);
  const [execStatusText, setExecStatusText] = useState<string>('Preparing cleanup...');
  const [executionResult, setExecutionResult] = useState<CleanupOperation | null>(null);
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [bannerSuccess, setBannerSuccess] = useState<string | null>(null);

  // Audit Log State
  const [operations, setOperations] = useState<CleanupOperation[]>([]);
  const [loadingOps, setLoadingOps] = useState<boolean>(false);
  const [undoingId, setUndoingId] = useState<number | null>(null);

  // Initialize query if passed from other views
  useEffect(() => {
    if (initialQuery) {
      setIsExternalQuery(true);
      handleCalculatePreview(initialQuery, true);
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

  const handleCalculatePreview = async (overrideAst?: QueryAST, fromExternal = false) => {
    setBannerError(null);
    setBannerSuccess(null);
    if (operationType === 'label' && !labelName.trim()) {
      setBannerError('Please enter a valid Gmail label name.');
      return;
    }
    const ast = overrideAst || buildQueryAST();
    if (!fromExternal) {
      setIsExternalQuery(false);
    }
    setActiveAst(ast);
    setCalculatingPreview(true);
    setExecutionResult(null);
    try {
      const res = await api.calculateCleanupPreview({
        account_id: accountId,
        operation_type: operationType,
        query: ast,
        label_name: operationType === 'label' ? labelName.trim() : undefined,
      });
      setPreview(res);
    } catch (err: any) {
      setBannerError(err.message || 'Failed to simulate cleanup preview');
    } finally {
      setCalculatingPreview(false);
    }
  };

  const handleResetExternalQuery = () => {
    setIsExternalQuery(false);
    setActiveAst(null);
    setPreview(null);
    onClearInitialQuery?.();
  };

  const handleExecuteOperation = async () => {
    if (!preview) return;
    setBannerError(null);
    if (operationType === 'label' && !labelName.trim()) {
      setBannerError('Please enter a valid Gmail label name.');
      return;
    }
    const astToExecute = activeAst || buildQueryAST();
    setExecuting(true);
    setExecProgress(15);
    setExecStatusText(
      operationType === 'label'
        ? 'Verifying target safe-lists and Gmail label parameters...'
        : 'Verifying target safe-lists and message UIDs...'
    );

    const timer1 = setTimeout(() => {
      setExecProgress(45);
      if (operationType === 'label') {
        setExecStatusText(`Applying label "${labelName.trim()}" on mail server...`);
      } else {
        setExecStatusText(`Moving messages to ${operationType === 'trash' ? 'Trash' : 'Archive'} on mail server...`);
      }
    }, 450);

    const timer2 = setTimeout(() => {
      setExecProgress(75);
      setExecStatusText(
        operationType === 'label'
          ? 'Synchronizing local label mappings and message records...'
          : 'Synchronizing local database records and folders...'
      );
    }, 1100);

    const timer3 = setTimeout(() => {
      setExecProgress(92);
      setExecStatusText('Finalizing audit logs and indexing...');
    }, 1800);

    try {
      const res = await api.executeCleanup({
        account_id: accountId ?? preview.account_id,
        operation_type: operationType,
        query: astToExecute,
        label_name: operationType === 'label' ? labelName.trim() : undefined,
      });
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setExecProgress(100);
      setExecStatusText('Operation finalized!');
      setExecutionResult(res);
      onOperationsChanged?.();

      setTimeout(() => {
        setConfirmModalOpen(false);
        setExecuting(false);
        setExecProgress(0);
        loadOperations();
      }, 400);
    } catch (err: any) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setBannerError(err.message || 'Error executing operation');
      setExecuting(false);
      setExecProgress(0);
    }
  };

  const handleUndo = async (operationId: number) => {
    setUndoingId(operationId);
    setBannerError(null);
    setBannerSuccess(null);
    try {
      const res = await api.undoCleanup(operationId);
      const op = operations.find((o) => o.id === operationId);
      if (op?.operation_type === 'label' || (operationType === 'label' && executionResult?.id === operationId)) {
        setBannerSuccess(`Successfully removed label from ${res.restored_count} messages.`);
      } else {
        setBannerSuccess(`Successfully restored ${res.restored_count} messages back to their original folders.`);
      }
      onOperationsChanged?.();
      await loadOperations();
    } catch (err: any) {
      setBannerError(err.message || 'Error executing undo');
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

      {bannerError && (
        <div className="px-6 py-2.5 bg-red-950/70 border-b border-red-700 text-red-200 text-xs font-mono flex items-center justify-between">
          <span>{bannerError}</span>
          <button onClick={() => setBannerError(null)} className="text-red-300 hover:text-white font-bold px-2">×</button>
        </div>
      )}

      {bannerSuccess && (
        <div className="px-6 py-2.5 bg-emerald-950/70 border-b border-emerald-700 text-emerald-200 text-xs font-mono flex items-center justify-between">
          <span>{bannerSuccess}</span>
          <button onClick={() => setBannerSuccess(null)} className="text-emerald-300 hover:text-white font-bold px-2">×</button>
        </div>
      )}

      {activeTab === 'builder' ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isExternalQuery && activeAst && (
            <div className="p-3.5 bg-brand/10 border border-brand/40 flex items-center justify-between text-xs font-mono">
              <div className="text-brand-light">
                <strong>Targeted Selection Active:</strong> Executing against the query handed off from Explorer / Graph / Insights ({activeAst.all?.length || 0} condition{(activeAst.all?.length || 0) === 1 ? '' : 's'}).
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button size="xs" variant="outline" onClick={() => handleCalculatePreview(activeAst, true)}>
                  Re-simulate with {operationType.toUpperCase()}
                </Button>
                <Button size="xs" variant="ghost" onClick={handleResetExternalQuery}>
                  Clear Selection
                </Button>
              </div>
            </div>
          )}

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
                  onChange={(e) => setOperationType(e.target.value as 'trash' | 'archive' | 'label')}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value="trash">Move to Trash (Recoverable)</option>
                  <option value="archive">Archive (Remove from Inbox)</option>
                  <option value="label">Apply Gmail Label (Tag in Gmail)</option>
                </select>
              </div>
            </div>

            {/* Label Name Selector for Gmail Label Operation */}
            {operationType === 'label' && (
              <div className="p-4 bg-bg-deep rounded border border-border-muted space-y-3 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <label className="text-slate-300 font-mono text-[11px] font-semibold flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-brand-light" />
                    GMAIL LABEL CONFIGURATION
                  </label>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2 py-0.5 rounded">
                    Non-Destructive • Reversible
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Preset Suggestions Dropdown */}
                  <div>
                    <label className="block text-slate-400 font-mono text-[11px] mb-1">
                      PRESET CATEGORY SUGGESTIONS
                    </label>
                    <select
                      value={PRESET_LABELS.includes(labelName) ? labelName : '__custom__'}
                      onChange={(e) => {
                        if (e.target.value !== '__custom__') {
                          setLabelName(e.target.value);
                        }
                      }}
                      className="w-full bg-bg-surface border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                    >
                      {PRESET_LABELS.map((preset) => (
                        <option key={preset} value={preset}>
                          {preset}
                        </option>
                      ))}
                      <option value="__custom__">Custom Label...</option>
                    </select>
                  </div>

                  {/* Custom Label Input Field */}
                  <div>
                    <label className="block text-slate-400 font-mono text-[11px] mb-1">
                      CUSTOM LABEL NAME
                    </label>
                    <input
                      type="text"
                      value={labelName}
                      onChange={(e) => setLabelName(e.target.value)}
                      placeholder="e.g. MailGraph/CustomTag"
                      className="w-full bg-bg-surface border border-border-muted rounded px-3 py-1.5 text-slate-200 placeholder-slate-600 focus:outline-none font-mono"
                    />
                  </div>
                </div>

                {/* Preset Chips */}
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[11px] font-mono text-slate-400 mr-1">Suggestions:</span>
                  {PRESET_LABELS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setLabelName(preset)}
                      className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                        labelName === preset
                          ? 'bg-brand text-white border border-brand'
                          : 'bg-bg-surface text-slate-400 hover:text-slate-200 border border-border-muted hover:border-slate-500'
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>
            )}

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
                    {operationType === 'label'
                      ? `${executionResult.completed_count} messages tagged with label "${labelName.trim()}". Undo is available.`
                      : `${executionResult.completed_count} messages moved to ${operationType}. Undo is available.`}
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
                  <div className="text-[11px] text-slate-400 font-mono">
                    {operationType === 'label' ? 'TARGET DATA SIZE' : 'ESTIMATED STORAGE'}
                  </div>
                  <div className="text-xl font-bold font-mono text-slate-100">
                    {(preview.total_size_bytes / (1024 * 1024)).toFixed(2)} MB
                  </div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">
                    {operationType === 'label' ? 'Non-destructive tag' : 'Reclaimable local storage'}
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
                    {preview.reversible ? '100% Recoverable' : 'Irreversible'}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate" title={preview.reversibility_note}>
                    {preview.reversibility_note || 'Logged in audit table'}
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
                  icon={
                    operationType === 'trash' ? (
                      <Trash2 className="w-4 h-4" />
                    ) : operationType === 'label' ? (
                      <Tag className="w-4 h-4" />
                    ) : (
                      <Archive className="w-4 h-4" />
                    )
                  }
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
            title={
              operationType === 'trash'
                ? 'Explicit Confirmation: Move to Trash'
                : operationType === 'archive'
                ? 'Explicit Confirmation: Archive'
                : 'Explicit Confirmation: Apply Gmail Label'
            }
            subtitle={
              operationType === 'label'
                ? 'Non-destructive labeling: verify label application before mutating mailbox tags'
                : 'Destructive safety requirement: verify your intent before mutating mailbox state'
            }
            maxWidth="lg"
          >
            <div className="space-y-4 text-xs">
              <div
                className={`p-3 rounded border flex items-start gap-2.5 ${
                  operationType === 'label'
                    ? 'bg-blue-950/30 border-blue-800/50 text-blue-200'
                    : 'bg-amber-950/30 border-amber-800/50 text-amber-200'
                }`}
              >
                {operationType === 'label' ? (
                  <Tag className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                )}
                <p>
                  {operationType === 'label' ? (
                    <>
                      You are about to apply label{' '}
                      <strong className="text-white font-mono">"{labelName.trim()}"</strong> to{' '}
                      <strong className="text-white font-mono">{preview?.target_count} messages</strong> (~
                      {preview ? (preview.total_size_bytes / (1024 * 1024)).toFixed(2) : 0} MB).
                    </>
                  ) : (
                    <>
                      You are about to {operationType === 'trash' ? 'move' : 'archive'}{' '}
                      <strong className="text-white font-mono">{preview?.target_count} messages</strong> (~
                      {preview ? (preview.total_size_bytes / (1024 * 1024)).toFixed(2) : 0} MB).
                    </>
                  )}
                </p>
              </div>

              <p className="text-slate-300 leading-relaxed font-sans">
                {operationType === 'label'
                  ? `MailGraph will create the label "${labelName.trim()}" if needed and attach it to matching messages in Gmail, logging the action for easy rollback.`
                  : 'MailGraph will sync this action with your live mailbox (moving messages to Trash on Gmail/IMAP) and snapshot the original state in local storage. You can undo this operation at any time from the Audit Trail tab.'}
              </p>

              <div className="p-3 bg-bg-deep rounded border border-border-subtle space-y-1 font-mono text-[11px]">
                <div className="text-slate-400">Target Query Summary:</div>
                {isExternalQuery && activeAst ? (
                  <div className="text-slate-200">
                    • Custom Selection Query ({activeAst.all?.map((c) => `${c.field} ${c.op} ${JSON.stringify(c.value)}`).join(' AND ') || 'Filtered set'})
                  </div>
                ) : (
                  <>
                    <div className="text-slate-200">• Category: {targetCategory || 'Any'}</div>
                    <div className="text-slate-200">• Age: {daysOld > 0 ? `Older than ${daysOld} days` : 'Any age'}</div>
                  </>
                )}
                {operationType === 'label' && (
                  <div className="text-brand-light font-semibold">• Target Label: {labelName.trim()}</div>
                )}
                <div className="text-slate-200">
                  • Protected Messages: Excluded ({preview?.protected_excluded_count} shielded)
                </div>
                {preview?.reversibility_note && (
                  <div className="text-emerald-400">• Reversibility: {preview.reversibility_note}</div>
                )}
              </div>

              {/* Real-time Progress Bar Card while executing cleanup */}
              {executing ? (
                <div className="p-4 bg-bg-surface border border-border-muted rounded-none space-y-3.5 shadow-xl animate-fadeIn font-mono">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <RefreshCw className="w-4 h-4 text-brand animate-spin" />
                      <span className="text-xs font-bold text-white uppercase">{execStatusText}</span>
                    </div>
                    <span className="text-xs font-mono font-bold text-brand">{execProgress}%</span>
                  </div>

                  {/* Progress bar track */}
                  <div className="w-full bg-bg-deep rounded-none h-3 overflow-hidden border border-border-muted p-0.5">
                    <div
                      className="bg-brand h-full rounded-none transition-all duration-300 ease-out"
                      style={{ width: `${Math.max(6, execProgress)}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                    <span>Processing {preview?.target_count?.toLocaleString()} messages</span>
                    <span>Live remote mailbox sync</span>
                  </div>
                </div>
              ) : (
                <div className="pt-3 border-t border-border-subtle flex justify-end gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setConfirmModalOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant={operationType === 'trash' ? 'danger' : 'primary'}
                    loading={executing}
                    onClick={handleExecuteOperation}
                    icon={operationType === 'label' ? <Tag className="w-4 h-4" /> : undefined}
                  >
                    {operationType === 'label'
                      ? `Apply Label "${labelName.trim()}" to ${preview?.target_count} Messages`
                      : `Yes, ${operationType === 'trash' ? 'Move' : 'Archive'} ${preview?.target_count} Messages`}
                  </Button>
                </div>
              )}
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
                            <span className="text-brand-light font-bold">Undone (Restored)</span>
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
