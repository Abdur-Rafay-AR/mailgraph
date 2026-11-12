import React, { useEffect, useState } from 'react';
import {
  Mail,
  Users,
  HardDrive,
  Clock,
  Sparkles,
  ArrowRight,
  Shield,
  GitFork,
  Trash2,
  AlertCircle
} from 'lucide-react';
import { api } from '../../api/client';
import { OverviewStats } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

interface OverviewViewProps {
  onNavigate: (view: any) => void;
  onOpenSenderMessages?: (senderAddress: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  onNavigate,
  onOpenSenderMessages,
}) => {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [demoLoading, setDemoLoading] = useState<boolean>(false);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await api.getOverview();
      setStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleGenerateDemo = async () => {
    setDemoLoading(true);
    try {
      await api.generateSynthetic({ message_count: 75 });
      await fetchStats();
    } catch (err: any) {
      alert(err.message || 'Failed to generate demo data');
    } finally {
      setDemoLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-slate-400 font-mono text-xs">
        Loading mailbox overview and local database statistics...
      </div>
    );
  }

  const totalMb = stats ? (stats.total_bytes / (1024 * 1024)).toFixed(1) : '0';

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-bg-deep select-none">
      {/* Empty State Banner if no messages exist */}
      {stats && stats.total_messages === 0 && (
        <div className="p-6 rounded-lg bg-bg-surface border border-brand/40 shadow-xl space-y-3">
          <div className="flex items-center gap-2.5 text-brand-light font-semibold text-sm">
            <Sparkles className="w-5 h-5 text-amber-400" />
            Welcome to MailGraph: No mailbox data indexed yet
          </div>
          <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
            MailGraph runs entirely offline on your local machine. You can import an offline MBOX archive, connect your Gmail or IMAP account, or instantly generate realistic synthetic demo data to test search, interactive graphs, and safe bulk cleanup workflows.
          </p>
          <div className="flex items-center gap-3 pt-2">
            <Button
              size="sm"
              variant="primary"
              loading={demoLoading}
              onClick={handleGenerateDemo}
              icon={<Sparkles className="w-4 h-4 text-amber-300" />}
            >
              Generate Synthetic Mailbox (75 emails)
            </Button>
            <Button size="sm" variant="outline" onClick={() => onNavigate('settings')}>
              Connect Account in Settings
            </Button>
          </div>
        </div>
      )}

      {/* Primary KPI Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Volume */}
        <div className="p-4 bg-bg-surface rounded-lg border border-border-subtle shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
            <span>TOTAL MESSAGES</span>
            <Mail className="w-4 h-4 text-brand-light" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {stats ? stats.total_messages.toLocaleString() : 0}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-1">
            {stats?.unread_messages ? `${stats.unread_messages.toLocaleString()} unread` : '0 unread'}
          </div>
        </div>

        {/* Local Storage */}
        <div className="p-4 bg-bg-surface rounded-lg border border-border-subtle shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
            <span>LOCAL FOOTPRINT</span>
            <HardDrive className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {totalMb} <span className="text-sm font-normal text-slate-400">MB</span>
          </div>
          <div className="text-[11px] text-emerald-400 font-mono mt-1">
            SQLite indexed offline
          </div>
        </div>

        {/* Senders & Organizations */}
        <div className="p-4 bg-bg-surface rounded-lg border border-border-subtle shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
            <span>SENDERS & DOMAINS</span>
            <Users className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {stats ? stats.total_senders : 0}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-1">
            across {stats ? stats.total_domains : 0} unique domains
          </div>
        </div>

        {/* Date Coverage */}
        <div className="p-4 bg-bg-surface rounded-lg border border-border-subtle shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
            <span>OBSERVED TIMELINE</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xs font-mono font-semibold text-slate-200 mt-2 truncate">
            {stats?.earliest_date?.slice(0, 10) || 'N/A'} to {stats?.latest_date?.slice(0, 10) || 'N/A'}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-1">
            Continuous history span
          </div>
        </div>
      </div>

      {/* Two Column Section: Top Senders vs Category Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Dominant Senders */}
        <div className="bg-bg-surface rounded-lg border border-border-subtle p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <Users className="w-4 h-4 text-brand-light" />
              Highest Volume Senders
            </h3>
            <button
              onClick={() => onNavigate('senders')}
              className="text-xs font-mono text-brand-light hover:underline flex items-center gap-1"
            >
              Browse All Senders <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="divide-y divide-border-subtle border border-border-subtle rounded">
            {stats?.top_senders_by_count && stats.top_senders_by_count.length > 0 ? (
              stats.top_senders_by_count.map((s) => (
                <div
                  key={s.id}
                  onClick={() => onOpenSenderMessages && onOpenSenderMessages(s.address)}
                  className="p-3 flex items-center justify-between hover:bg-bg-elevated cursor-pointer transition-colors text-xs"
                >
                  <div className="truncate max-w-xs font-sans">
                    <div className="font-medium text-slate-200 truncate">{s.name}</div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">{s.address}</div>
                  </div>
                  <div className="text-right font-mono">
                    <div className="font-semibold text-slate-200">{s.message_count.toLocaleString()} msgs</div>
                    <div className="text-[10px] text-slate-500">{(s.total_bytes / 1024).toFixed(0)} KB</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-xs text-slate-500 font-sans">
                No sender activity recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="bg-bg-surface rounded-lg border border-border-subtle p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              Category Classification Breakdown
            </h3>
            <button
              onClick={() => onNavigate('messages')}
              className="text-xs font-mono text-brand-light hover:underline flex items-center gap-1"
            >
              Filter in Explorer <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-2.5">
            {stats?.categories && stats.categories.length > 0 ? (
              stats.categories.map((cat) => {
                const pct = stats.total_messages > 0 ? ((cat.count / stats.total_messages) * 100).toFixed(1) : 0;
                return (
                  <div key={cat.name} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="capitalize text-slate-300">{cat.name.replace('_', ' ')}</span>
                      <span className="text-slate-400">{cat.count} ({pct}%)</span>
                    </div>
                    <div className="w-full h-1.5 bg-bg-deep rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: cat.color || '#9061f9',
                        }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="py-6 text-center text-xs text-slate-500 font-sans">
                No categorized messages.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Launch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        <div
          onClick={() => onNavigate('graph')}
          className="p-4 rounded-lg bg-bg-surface border border-border-subtle hover:border-brand/60 cursor-pointer transition-all shadow-sm space-y-1.5 group"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm text-slate-100 group-hover:text-brand-light transition-colors">
              Interactive Graph Explorer
            </span>
            <GitFork className="w-4 h-4 text-brand-light" />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Visualize relationships across organizational domains, active senders, and conversation reply chains.
          </p>
        </div>

        <div
          onClick={() => onNavigate('senders')}
          className="p-4 rounded-lg bg-bg-surface border border-border-subtle hover:border-brand/60 cursor-pointer transition-all shadow-sm space-y-1.5 group"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm text-slate-100 group-hover:text-brand-light transition-colors">
              Dedicated Sender Management
            </span>
            <Users className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Sort senders by message volume and storage contribution, select candidates, and preview bulk cleanup.
          </p>
        </div>

        <div
          onClick={() => onNavigate('cleanup')}
          className="p-4 rounded-lg bg-bg-surface border border-border-subtle hover:border-brand/60 cursor-pointer transition-all shadow-sm space-y-1.5 group"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm text-slate-100 group-hover:text-brand-light transition-colors">
              Safe Cleanup Studio
            </span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Build queries with protection exclusions, review exact simulation previews, and execute reversible trash/archive.
          </p>
        </div>
      </div>
    </div>
  );
};
