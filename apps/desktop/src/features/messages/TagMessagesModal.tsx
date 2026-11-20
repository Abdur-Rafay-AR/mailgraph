import React, { useState, useEffect } from 'react';
import { Tag, Shield, AlertTriangle, Eye, CheckCircle2 } from 'lucide-react';
import { Modal } from '../../components/Modal';
import { Button } from '../../components/Button';
import { api } from '../../api/client';
import { QueryAST, CleanupPreview, CleanupOperation } from '../../types/api';

const PRESET_LABELS = [
  'MailGraph/Finance',
  'MailGraph/Receipts',
  'MailGraph/Work',
  'MailGraph/Personal',
  'MailGraph/Newsletters',
  'MailGraph/Security',
  'MailGraph/FollowUp',
];

export interface TagMessagesModalProps {
  isOpen: boolean;
  onClose: () => void;
  query: QueryAST | null;
  targetCount: number;
  isSelection: boolean;
  accountId?: number;
  onSuccess: (operation: CleanupOperation, labelName: string) => void;
}

export const TagMessagesModal: React.FC<TagMessagesModalProps> = ({
  isOpen,
  onClose,
  query,
  targetCount,
  isSelection,
  accountId,
  onSuccess,
}) => {
  const [labelName, setLabelName] = useState<string>('MailGraph/Tag');
  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [executing, setExecuting] = useState<boolean>(false);
  const [executeError, setExecuteError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setPreview(null);
      setPreviewLoading(false);
      setPreviewError(null);
      setExecuting(false);
      setExecuteError(null);
      if (!labelName) {
        setLabelName('MailGraph/Tag');
      }
    }
  }, [isOpen]);

  if (!isOpen || !query) return null;

  const handlePreview = async () => {
    const trimmed = labelName.trim();
    if (!trimmed) {
      setPreviewError('Please enter a valid Gmail label name.');
      return;
    }

    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await api.previewCleanup({
        account_id: accountId,
        operation_type: 'label',
        label_name: trimmed,
        query,
      });
      setPreview(res);
    } catch (err: any) {
      setPreviewError(err.message || 'Failed to simulate cleanup preview');
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirmTag = async () => {
    const trimmed = labelName.trim();
    if (!trimmed) {
      setExecuteError('Please enter a valid Gmail label name.');
      return;
    }

    setExecuting(true);
    setExecuteError(null);
    try {
      const operation = await api.executeCleanup({
        account_id: accountId,
        operation_type: 'label',
        label_name: trimmed,
        query,
      });
      onSuccess(operation, trimmed);
      onClose();
    } catch (err: any) {
      setExecuteError(err.message || 'Error executing Gmail label operation');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={executing ? () => {} : onClose}
      title="Tag in Gmail"
      subtitle={
        isSelection
          ? `Tagging ${targetCount} selected message${targetCount === 1 ? '' : 's'}`
          : `Tagging ${targetCount.toLocaleString()} matching message${targetCount === 1 ? '' : 's'}`
      }
      maxWidth="lg"
    >
      <div className="space-y-4 text-xs font-sans">
        {/* Target summary banner */}
        <div className="p-3 bg-bg-deep rounded border border-border-subtle flex items-start justify-between gap-3 font-mono">
          <div>
            <div className="text-slate-400 text-[11px] uppercase tracking-wider">Target Scope</div>
            <div className="text-sm font-semibold text-slate-100 mt-0.5">
              {isSelection
                ? `${targetCount} Selected Message${targetCount === 1 ? '' : 's'}`
                : `${targetCount.toLocaleString()} Message${targetCount === 1 ? '' : 's'} (Current Search)`}
            </div>
          </div>
          <div className="text-right">
            <div className="text-slate-400 text-[11px] uppercase tracking-wider">Protection Shield</div>
            <div className="mt-0.5 inline-flex items-center gap-1">
              <Shield className={`w-3.5 h-3.5 ${query.exclude_protected ? 'text-emerald-400' : 'text-red-400'}`} />
              <span className={`text-xs font-medium ${query.exclude_protected ? 'text-emerald-400' : 'text-red-400'}`}>
                {query.exclude_protected ? 'Protected Shield: ON' : 'Protected Shield: OFF'}
              </span>
            </div>
          </div>
        </div>

        {/* Label Selector */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5 text-brand-light" />
              Gmail Label Name
            </label>
            <span className="text-[11px] text-slate-500 font-mono">Select preset or type custom</span>
          </div>

          {/* Preset chips */}
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {PRESET_LABELS.map((preset) => (
              <button
                key={preset}
                type="button"
                disabled={executing}
                onClick={() => {
                  setLabelName(preset);
                  setPreview(null);
                }}
                className={`px-2.5 py-1 rounded text-xs font-mono transition-colors border ${
                  labelName === preset
                    ? 'bg-brand/25 border-brand text-brand-light font-semibold shadow-sm'
                    : 'bg-bg-deep border-border-muted text-slate-300 hover:text-white hover:border-slate-500'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {preset}
              </button>
            ))}
          </div>

          {/* Custom text input */}
          <div className="relative pt-1">
            <Tag className="w-4 h-4 text-slate-400 absolute left-3 top-3.5" />
            <input
              type="text"
              value={labelName}
              disabled={executing}
              onChange={(e) => {
                setLabelName(e.target.value);
                setPreview(null);
              }}
              placeholder="MailGraph/Tag"
              className="w-full pl-9 pr-3 py-2 bg-bg-deep border border-border-muted rounded text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-light disabled:opacity-50"
            />
          </div>
          <p className="text-[11px] text-slate-400 font-sans">
            Labels can use '/' to create nested sub-folders in Gmail (e.g.{' '}
            <span className="font-mono text-slate-300">MailGraph/Receipts/2026</span>). Non-existing labels will be
            automatically created.
          </p>
        </div>

        {/* Simulation Preview Card */}
        {preview && (
          <div className="p-3.5 bg-bg-deep rounded border border-border-subtle space-y-2.5 font-mono animate-fadeIn">
            <div className="flex items-center justify-between text-brand-light font-semibold border-b border-border-subtle pb-2">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Preview Simulation
              </span>
              <span className="text-slate-300 text-xs">Label: "{labelName.trim()}"</span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="bg-bg-surface p-2.5 rounded border border-border-subtle">
                <span className="text-slate-400 block">Simulated Target</span>
                <span className="text-white font-bold text-base">{preview.target_count.toLocaleString()}</span>
                <span className="text-slate-500 block text-[10px]">
                  ~{(preview.total_size_bytes / (1024 * 1024)).toFixed(2)} MB affected
                </span>
              </div>
              <div className="bg-bg-surface p-2.5 rounded border border-border-subtle">
                <span className="text-slate-400 block">Excluded by Shield</span>
                <span className="text-emerald-400 font-bold text-base">
                  {preview.protected_excluded_count.toLocaleString()}
                </span>
                <span className="text-slate-500 block text-[10px]">Protected senders / starred</span>
              </div>
            </div>

            {preview.reversibility_note && (
              <div className="text-[11px] text-slate-300 font-sans pt-1">
                <span className="text-emerald-400 font-mono font-semibold">Reversibility: </span>
                {preview.reversibility_note}
              </div>
            )}

            {preview.top_senders && preview.top_senders.length > 0 && (
              <div className="pt-1.5 border-t border-border-subtle">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                  Top Senders Affected:
                </span>
                <div className="space-y-1 max-h-24 overflow-y-auto pr-1">
                  {preview.top_senders.slice(0, 3).map((sender, idx) => (
                    <div key={idx} className="flex items-center justify-between text-[11px] text-slate-300">
                      <span className="truncate max-w-[240px] font-sans">{sender.name || sender.address}</span>
                      <span className="text-slate-400 font-mono shrink-0">{sender.count} msgs</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error Cards */}
        {previewError && (
          <div className="p-3 rounded bg-red-950/40 border border-red-800 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{previewError}</span>
          </div>
        )}

        {executeError && (
          <div className="p-3 rounded bg-red-950/40 border border-red-800 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{executeError}</span>
          </div>
        )}

        {/* Loading execution indicator */}
        {executing && (
          <div className="p-3 bg-brand/10 border border-brand/40 rounded flex items-center gap-3 text-brand-light font-mono text-xs animate-pulse">
            <svg className="animate-spin h-4 w-4 text-brand-light shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
            </svg>
            <span>Applying label "{labelName.trim()}" in Gmail and syncing local index...</span>
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-border-subtle mt-2">
          <Button size="sm" variant="ghost" onClick={onClose} disabled={executing}>
            Cancel
          </Button>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              icon={<Eye className="w-3.5 h-3.5" />}
              loading={previewLoading}
              disabled={executing || !labelName.trim()}
              onClick={handlePreview}
            >
              Preview
            </Button>

            <Button
              size="sm"
              variant="primary"
              icon={<Tag className="w-3.5 h-3.5" />}
              loading={executing}
              disabled={executing || !labelName.trim()}
              onClick={handleConfirmTag}
            >
              Confirm & Tag in Gmail
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
