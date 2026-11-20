import React, { useEffect, useMemo, useState } from 'react';
import {
  Tag,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  RefreshCw,
  CheckSquare,
  Square,
  Layers,
} from 'lucide-react';
import { api } from '../../api/client';
import {
  Account,
  CategorySyncPreview,
  CategorySyncExecuteResponse,
  CategorySyncUndoResponse,
} from '../../types';
import { Modal } from '../../components/Modal';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

export interface CategorySyncModalProps {
  isOpen: boolean;
  onClose: () => void;
  accountId?: number;
  accounts?: Account[];
  onSyncSuccess?: () => void;
}

export const CategorySyncModal: React.FC<CategorySyncModalProps> = ({
  isOpen,
  onClose,
  accountId,
  accounts = [],
  onSyncSuccess,
}) => {
  const activeAccounts = useMemo(
    () => accounts.filter((a) => a.status !== 'paused'),
    [accounts]
  );

  const defaultAccountId = useMemo(() => {
    if (accountId !== undefined) return accountId;
    const preferred = activeAccounts.find((a) => a.provider === 'gmail' || a.provider === 'imap');
    return preferred?.id ?? activeAccounts[0]?.id;
  }, [accountId, activeAccounts]);

  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(defaultAccountId);
  const effectiveAccountId = accountId ?? selectedAccountId ?? defaultAccountId;

  // Preview state
  const [preview, setPreview] = useState<CategorySyncPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Selection state
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

  // Execution state
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncProgress, setSyncProgress] = useState<number>(0);
  const [syncStatusText, setSyncStatusText] = useState<string>('Preparing category sync...');
  const [syncResult, setSyncResult] = useState<CategorySyncExecuteResponse | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  // Undo state
  const [undoing, setUndoing] = useState<boolean>(false);
  const [undoResult, setUndoResult] = useState<CategorySyncUndoResponse | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);

  const loadPreview = async (targetAccountId?: number) => {
    const accToUse = targetAccountId ?? effectiveAccountId;
    if (!accToUse) {
      setPreview(null);
      setLoadingPreview(false);
      setPreviewError('No active account found. Connect or enable an account in Settings first.');
      return;
    }
    setLoadingPreview(true);
    setPreviewError(null);
    setSyncResult(null);
    setUndoResult(null);
    setSyncError(null);
    setUndoError(null);

    try {
      const data = await api.previewCategorySync(accToUse);
      setPreview(data);
      setSelectedCategories(data.categories.map((c) => c.category));
    } catch (err: any) {
      console.error(err);
      setPreviewError(err.message || 'Failed to fetch category sync preview.');
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      const initialAcc = accountId ?? defaultAccountId;
      setSelectedAccountId(initialAcc);
      loadPreview(initialAcc);
    } else {
      setSyncResult(null);
      setUndoResult(null);
      setSyncError(null);
      setUndoError(null);
      setSyncing(false);
      setUndoing(false);
    }
  }, [isOpen, accountId, defaultAccountId]);

  const toggleCategory = (category: string) => {
    if (syncing) return;
    setSelectedCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
    );
  };

  const handleSelectAll = () => {
    if (!preview || syncing) return;
    setSelectedCategories(preview.categories.map((c) => c.category));
  };

  const handleDeselectAll = () => {
    if (syncing) return;
    setSelectedCategories([]);
  };

  const selectedCount = useMemo(() => {
    if (!preview) return 0;
    return preview.categories
      .filter((c) => selectedCategories.includes(c.category))
      .reduce((sum, c) => sum + c.count, 0);
  }, [preview, selectedCategories]);

  const handleExecuteSync = async () => {
    if (!preview || selectedCategories.length === 0 || syncing) return;
    setSyncing(true);
    setSyncError(null);
    setSyncProgress(20);
    setSyncStatusText('Connecting to mailbox provider & creating labels...');

    const timer1 = setTimeout(() => {
      setSyncProgress(55);
      setSyncStatusText('Tagging messages with MailGraph category labels...');
    }, 450);

    const timer2 = setTimeout(() => {
      setSyncProgress(85);
      setSyncStatusText('Updating local index and audit records...');
    }, 1100);

    try {
      if (!effectiveAccountId) {
        setSyncError('No active account selected.');
        setSyncing(false);
        return;
      }
      const res = await api.executeCategorySync(effectiveAccountId, selectedCategories);
      clearTimeout(timer1);
      clearTimeout(timer2);
      setSyncProgress(100);
      setSyncStatusText('Complete');
      setSyncResult(res);
      onSyncSuccess?.();
    } catch (err: any) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      console.error(err);
      setSyncError(err.message || 'Failed to sync categories to Gmail.');
    } finally {
      setSyncing(false);
    }
  };

  const handleUndo = async () => {
    if (!syncResult || undoing) return;
    setUndoing(true);
    setUndoError(null);

    try {
      if (!effectiveAccountId) return;
      const res = await api.undoCategorySync(effectiveAccountId, syncResult.batch_id);
      setUndoResult(res);
      onSyncSuccess?.();
    } catch (err: any) {
      console.error(err);
      setUndoError(err.message || 'Failed to undo category sync.');
    } finally {
      setUndoing(false);
    }
  };

  const formatCategoryName = (name: string) => {
    return name
      .split('_')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={syncing ? () => {} : onClose}
      title="Gmail Category Sync"
      subtitle="Organize your Gmail inbox by applying MailGraph categories as native Gmail labels"
      maxWidth="2xl"
    >
      <div className="space-y-5">
        {/* Account Picker when scoped to All Accounts and multiple active accounts exist */}
        {accountId === undefined && activeAccounts.length > 1 && !syncResult && (
          <div className="flex items-center justify-between gap-3 p-3 bg-bg-deep border border-border-subtle text-xs font-mono">
            <span className="text-slate-400">Target Account:</span>
            <select
              value={effectiveAccountId ?? ''}
              disabled={syncing || loadingPreview}
              onChange={(e) => {
                const nextId = Number(e.target.value);
                setSelectedAccountId(nextId);
                loadPreview(nextId);
              }}
              className="bg-bg-surface border border-border-muted px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand"
            >
              {activeAccounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.display_name} ({acc.email_address})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Loading Preview State */}
        {loadingPreview && (
          <div className="py-14 flex flex-col items-center justify-center text-slate-400 font-mono text-xs space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin text-brand" />
            <span>Analyzing classified emails and Gmail labels...</span>
          </div>
        )}

        {/* Error Fetching Preview */}
        {!loadingPreview && previewError && (
          <div className="p-4 bg-red-950/60 border border-red-600 rounded-none space-y-3">
            <div className="flex items-start gap-3 text-red-200">
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="font-bold font-sans text-sm uppercase">Unable to Load Sync Preview</div>
                <div className="font-mono text-xs text-red-300 leading-relaxed">{previewError}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 pt-1 font-mono">
              <Button size="sm" variant="outline" onClick={() => loadPreview()} icon={<RefreshCw className="w-3 h-3" />}>
                Retry
              </Button>
              <Button size="sm" variant="ghost" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        )}

        {/* Execution Success / Undo Screen */}
        {!loadingPreview && !previewError && syncResult && (
          <div className="space-y-5">
            <div className="p-5 bg-emerald-950/30 border border-emerald-600/50 rounded-none space-y-4">
              <div className="flex items-start gap-3.5">
                <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-emerald-300 uppercase font-sans">
                    Category Sync Complete
                  </h4>
                  <p className="text-xs text-slate-200 font-mono leading-relaxed">
                    Successfully applied {syncResult.labeled_count.toLocaleString()} labels to your Gmail inbox across{' '}
                    {selectedCategories.length} categories.
                  </p>
                  <div className="text-[11px] text-slate-400 font-mono pt-1">
                    Batch ID: <span className="text-slate-200">{syncResult.batch_id}</span>
                  </div>
                </div>
              </div>

              {undoResult ? (
                <div className="p-3 bg-bg-surface border border-border-muted flex items-center gap-2.5 text-xs font-mono text-slate-300">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>
                    Rollback successful: Removed labels from {undoResult.undone_count.toLocaleString()} messages in Gmail.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-emerald-900/40">
                  <span className="text-xs text-slate-400 font-mono">
                    Labels can be safely reverted at any time:
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleUndo}
                    loading={undoing}
                    disabled={undoing}
                    icon={<RotateCcw className="w-3.5 h-3.5 text-amber-400" />}
                  >
                    {undoing ? 'Reverting Labels...' : 'Undo Sync'}
                  </Button>
                </div>
              )}

              {undoError && (
                <div className="p-3 bg-red-950/60 border border-red-600 text-red-200 text-xs font-mono flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                  <span>{undoError}</span>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="primary" size="md" onClick={onClose}>
                Done
              </Button>
            </div>
          </div>
        )}

        {/* Normal Category Selection & Sync Screen */}
        {!loadingPreview && !previewError && !syncResult && preview && (
          <div className="space-y-4">
            {/* Informational Summary Card */}
            <div className="p-4 bg-bg-elevated border border-border-subtle rounded-none space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-bold text-white uppercase font-sans">
                  <Tag className="w-4 h-4 text-brand" />
                  <span>Total Classified Emails Ready:</span>
                  <span className="text-brand-light font-mono font-bold">
                    {preview.total_messages.toLocaleString()}
                  </span>
                </div>
                <div className="text-xs font-mono text-slate-300">
                  Selected for Sync:{' '}
                  <span className="text-white font-semibold">{selectedCount.toLocaleString()} emails</span>
                </div>
              </div>
              <p className="text-xs text-slate-400 font-mono leading-relaxed">
                Tags will be created and applied under the <span className="text-slate-200">MailGraph/</span> Gmail label hierarchy (e.g.{' '}
                <span className="text-brand-light">MailGraph/Finance</span>). Your emails stay safely in your inbox and folders.
              </p>
            </div>

            {/* Category Checklist Controls */}
            {preview.categories.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500 font-mono border border-border-subtle p-4 bg-bg-surface">
                No categorized emails found. Ensure mailbox ingestion has indexed messages and classification has completed.
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-sans flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    Categories ({selectedCategories.length}/{preview.categories.length} selected)
                  </div>
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <button
                      type="button"
                      onClick={handleSelectAll}
                      disabled={syncing || selectedCategories.length === preview.categories.length}
                      className="text-brand-light hover:underline disabled:text-slate-600 disabled:no-underline cursor-pointer"
                    >
                      Select All
                    </button>
                    <span className="text-slate-600">•</span>
                    <button
                      type="button"
                      onClick={handleDeselectAll}
                      disabled={syncing || selectedCategories.length === 0}
                      className="text-slate-400 hover:text-white disabled:text-slate-600 disabled:no-underline cursor-pointer"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>

                {/* Categories Table / List */}
                <div className="border border-border-subtle max-h-64 overflow-y-auto divide-y divide-border-subtle bg-bg-surface">
                  {preview.categories.map((item) => {
                    const isSelected = selectedCategories.includes(item.category);
                    return (
                      <div
                        key={item.category}
                        onClick={() => toggleCategory(item.category)}
                        className={`p-3 flex items-center justify-between gap-3 text-xs font-mono transition-colors cursor-pointer select-none ${
                          isSelected ? 'bg-bg-elevated/70 hover:bg-bg-highlight' : 'opacity-65 hover:opacity-100 hover:bg-bg-elevated/30'
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <button
                            type="button"
                            className="text-slate-400 hover:text-white shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleCategory(item.category);
                            }}
                          >
                            {isSelected ? (
                              <CheckSquare className="w-4 h-4 text-brand-light" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-500" />
                            )}
                          </button>
                          <div className="truncate">
                            <span className="font-semibold text-slate-200 font-sans mr-2">
                              {formatCategoryName(item.category)}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                          <span className="px-2 py-0.5 text-[11px] bg-brand/10 border border-brand/30 text-brand-light font-mono rounded-none">
                            {item.label}
                          </span>
                          <span className="text-slate-300 font-semibold min-w-20 text-right">
                            {item.count.toLocaleString()} msgs
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Sync Progress Bar */}
            {syncing && (
              <div className="space-y-2 p-3.5 bg-bg-deep border border-border-muted rounded-none">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-200 flex items-center gap-2">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-brand" />
                    {syncStatusText}
                  </span>
                  <span className="text-brand font-bold">{syncProgress}%</span>
                </div>
                <div className="w-full bg-bg-surface h-2 border border-border-subtle rounded-none overflow-hidden">
                  <div
                    className="bg-brand h-full transition-all duration-300 ease-out"
                    style={{ width: `${syncProgress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Execution Error Banner */}
            {syncError && (
              <div className="p-3 bg-red-950/60 border border-red-600 text-red-200 text-xs font-mono flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold">Sync Failed</div>
                  <div>{syncError}</div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-border-subtle">
              <Button
                variant="ghost"
                size="md"
                onClick={onClose}
                disabled={syncing}
              >
                Cancel
              </Button>

              <Button
                variant="primary"
                size="md"
                onClick={handleExecuteSync}
                loading={syncing}
                disabled={selectedCategories.length === 0 || syncing || preview.categories.length === 0}
                icon={<Sparkles className="w-4 h-4 text-white" />}
              >
                {selectedCategories.length === 0
                  ? 'Select Categories to Sync'
                  : `Sync ${selectedCount.toLocaleString()} Emails to Gmail`}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
