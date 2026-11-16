import React from 'react';
import { RefreshCw, Database, Square, Mail } from 'lucide-react';
import { Button } from './Button';
import { Account, SyncJob } from '../types/api';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  onSyncMailbox?: () => void;
  loading?: boolean;
  onQuickDemo?: () => void;
  backendOnline?: boolean;
  activeSyncJob?: SyncJob | null;
  onStopSync?: () => void;
  accounts?: Account[];
  selectedAccountId?: number | 'all';
  onSelectAccount?: (id: number | 'all') => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  onRefresh,
  onSyncMailbox,
  loading = false,
  onQuickDemo,
  backendOnline = true,
  activeSyncJob,
  onStopSync,
  accounts = [],
  selectedAccountId = 'all',
  onSelectAccount,
}) => {
  const isSyncActive = Boolean(
    activeSyncJob &&
    (activeSyncJob.status === 'starting' ||
      activeSyncJob.status === 'running' ||
      activeSyncJob.status === 'stopping')
  );

  return (
    <header className="h-14 bg-bg-surface border-b border-border-subtle px-6 flex items-center justify-between shrink-0 select-none">
      <div className="flex items-center gap-6">
        <div>
          <h1 className="text-sm font-bold text-white tracking-wider uppercase font-sans flex items-center gap-2">
            {title}
            <span
              className={`w-2 h-2 rounded-none inline-block ${
                backendOnline ? 'bg-emerald-400' : 'bg-brand animate-pulse'
              }`}
              title={backendOnline ? 'Backend service online' : 'Backend offline'}
            />
          </h1>
          {subtitle && <p className="text-xs text-slate-400 font-mono mt-0.5">{subtitle}</p>}
        </div>

        {/* Global Account Switcher */}
        {accounts.length > 0 && onSelectAccount && (
          <div className="flex items-center gap-2 pl-4 border-l border-border-subtle">
            <Mail className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedAccountId}
              onChange={(e) => {
                const val = e.target.value;
                onSelectAccount(val === 'all' ? 'all' : Number(val));
              }}
              className="bg-bg-deep border border-border-subtle text-slate-200 text-xs px-2.5 py-1 rounded-none font-mono focus:outline-none focus:border-brand cursor-pointer hover:border-border-muted transition-colors"
              title="Scope all views to a specific account"
            >
              <option value="all">All Accounts ({accounts.filter((a) => a.status !== 'paused').length} Active)</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.display_name} ({acc.email_address}){acc.status === 'paused' ? ' [Disabled]' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Real-time Ingestion Progress HUD (visible across all tabs) */}
        {isSyncActive && activeSyncJob && (
          <div className="flex items-center gap-3 bg-bg-deep border border-border-muted px-3 py-1.5 rounded-none text-xs font-mono shadow-sm">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-none bg-brand animate-ping" />
              <span className="text-white font-bold tracking-tight">
                {activeSyncJob.is_all ? 'DIGESTING ALL' : 'DIGESTING'}:
              </span>
              <span
                className="text-slate-300 truncate max-w-[130px]"
                title={activeSyncJob.email_address}
              >
                {activeSyncJob.email_address}
              </span>
            </div>

            <div className="flex items-center gap-2 tabular-nums">
              <div className="w-28 bg-bg-surface border border-border-subtle h-2.5 overflow-hidden rounded-none">
                <div
                  className="bg-brand h-full transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(0, activeSyncJob.pct))}%` }}
                />
              </div>
              <span className="text-white font-bold font-mono">
                {activeSyncJob.scanned_count}
                {activeSyncJob.total_count > 0 ? ` / ${activeSyncJob.total_count}` : ''}
              </span>
              <span className="text-slate-400 text-[10px]">({activeSyncJob.pct}%)</span>
              {activeSyncJob.speed > 0 && (
                <span className="text-slate-500 text-[10px] hidden md:inline">
                  {activeSyncJob.speed} msg/s
                </span>
              )}
            </div>

            {onStopSync && (
              <Button
                size="xs"
                variant="danger"
                onClick={onStopSync}
                disabled={activeSyncJob.status === 'stopping'}
                icon={<Square className="w-2.5 h-2.5 fill-current" />}
                title="Halt ingestion immediately"
              >
                {activeSyncJob.status === 'stopping' ? 'Stopping...' : 'Stop'}
              </Button>
            )}
          </div>
        )}

        {onQuickDemo && (
          <Button
            size="sm"
            variant="outline"
            onClick={onQuickDemo}
            icon={<Database className="w-3.5 h-3.5 text-slate-300" />}
          >
            Load Demo Data
          </Button>
        )}

        {onSyncMailbox && (
          <Button
            size="sm"
            variant="primary"
            onClick={onSyncMailbox}
            loading={isSyncActive}
            disabled={isSyncActive}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isSyncActive ? 'animate-spin' : ''}`} />}
            title="Sync latest emails from connected mailbox"
          >
            {isSyncActive ? 'Syncing...' : 'Sync Mailbox'}
          </Button>
        )}

        {onRefresh && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onRefresh}
            loading={loading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            title="Refresh View"
          >
            Refresh
          </Button>
        )}
      </div>
    </header>
  );
};
