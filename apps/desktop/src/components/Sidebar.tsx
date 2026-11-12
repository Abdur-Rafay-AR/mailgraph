import React from 'react';
import {
  LayoutDashboard,
  GitFork,
  Mail,
  Users,
  Clock,
  Paperclip,
  ShieldCheck,
  Lightbulb,
  Settings,
  HardDrive
} from 'lucide-react';
import clsx from 'clsx';

export type NavView =
  | 'overview'
  | 'graph'
  | 'messages'
  | 'senders'
  | 'timeline'
  | 'attachments'
  | 'cleanup'
  | 'insights'
  | 'settings';

interface SidebarProps {
  currentView: NavView;
  onSelectView: (view: NavView) => void;
  storageMb?: string;
  totalMessages?: number;
}

const NAV_ITEMS: { id: NavView; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'graph', label: 'Graph Explorer', icon: GitFork },
  { id: 'messages', label: 'Messages', icon: Mail },
  { id: 'senders', label: 'Senders', icon: Users },
  { id: 'cleanup', label: 'Cleanup Studio', icon: ShieldCheck },
  { id: 'timeline', label: 'Timeline', icon: Clock },
  { id: 'attachments', label: 'Attachments', icon: Paperclip },
  { id: 'insights', label: 'Insights', icon: Lightbulb },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  storageMb,
  totalMessages,
}) => {
  return (
    <aside className="w-56 bg-bg-surface border-r border-border-subtle flex flex-col justify-between shrink-0 h-full select-none">
      {/* Brand & App Title */}
      <div>
        <div className="px-4 py-4 border-b border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-brand/20 border border-brand/40 flex items-center justify-center text-brand-light">
              <GitFork className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-slate-100">MailGraph</div>
              <div className="text-[10px] text-slate-500 font-mono tracking-widest uppercase">Local-First</div>
            </div>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-bg-elevated border border-border-muted text-slate-400">
            v0.1
          </span>
        </div>

        {/* Navigation list */}
        <nav className="p-2 space-y-1 mt-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className={clsx(
                  'w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs font-medium transition-colors text-left',
                  isActive
                    ? 'bg-brand/15 text-brand-light border border-brand/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-bg-elevated border border-transparent'
                )}
              >
                <Icon className={clsx('w-4 h-4 shrink-0', isActive ? 'text-brand-light' : 'text-slate-400')} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Local storage status pill */}
      <div className="p-3 border-t border-border-subtle">
        <div className="p-2.5 rounded bg-bg-deep border border-border-subtle text-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5 font-mono text-[11px]">
              <HardDrive className="w-3.5 h-3.5 text-slate-500" />
              Local Storage
            </span>
            <span className="text-emerald-400 font-mono text-[10px]">Active</span>
          </div>
          <div className="text-slate-200 font-mono text-xs font-semibold">
            {totalMessages ? totalMessages.toLocaleString() : '0'} msgs
          </div>
          {storageMb && (
            <div className="text-[10px] text-slate-500 font-mono mt-0.5">{storageMb} MB indexed</div>
          )}
        </div>
      </div>
    </aside>
  );
};
