import React from 'react';
import { RefreshCw, Shield, Sparkles } from 'lucide-react';
import { Button } from './Button';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  loading?: boolean;
  onQuickDemo?: () => void;
  backendOnline?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  onRefresh,
  loading = false,
  onQuickDemo,
  backendOnline = true,
}) => {
  return (
    <header className="h-14 bg-bg-surface border-b border-border-subtle px-6 flex items-center justify-between shrink-0 select-none">
      <div>
        <h1 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
          {title}
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              backendOnline ? 'bg-emerald-500' : 'bg-red-500 animate-pulse'
            }`}
            title={backendOnline ? 'Backend service online' : 'Backend offline'}
          />
        </h1>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2.5">
        {onQuickDemo && (
          <Button
            size="sm"
            variant="outline"
            onClick={onQuickDemo}
            icon={<Sparkles className="w-3.5 h-3.5 text-amber-400" />}
          >
            Load Demo Data
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
