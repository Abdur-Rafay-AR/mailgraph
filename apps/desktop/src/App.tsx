import React, { useState, useEffect, useRef } from 'react';
import { Sidebar, NavView } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewView } from './features/overview/OverviewView';
import { GraphView } from './features/graph/GraphView';
import { MessagesView } from './features/messages/MessagesView';
import { SendersView } from './features/senders/SendersView';
import { CleanupStudio } from './features/cleanup/CleanupStudio';
import { TimelineView } from './features/timeline/TimelineView';
import { AttachmentsView } from './features/attachments/AttachmentsView';
import { InsightsView } from './features/insights/InsightsView';
import { SettingsView } from './features/settings/SettingsView';
import { api } from './api/client';
import { Account, OverviewStats, QueryAST, SyncJob } from './types/api';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('overview');
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Global accounts & filtering state
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | 'all'>('all');
  const scopedAccountId = selectedAccountId === 'all' ? undefined : selectedAccountId;

  // Cross-view state handoffs
  const [messagesSenderFilter, setMessagesSenderFilter] = useState<string>('');
  const [cleanupInitialQuery, setCleanupInitialQuery] = useState<QueryAST | undefined>(undefined);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Global background ingestion state & auto-refresh trigger
  const [activeSyncJob, setActiveSyncJob] = useState<SyncJob | null>(null);
  const [syncRefreshTrigger, setSyncRefreshTrigger] = useState<number>(0);
  const scopedAccountIdRef = useRef<number | undefined>(scopedAccountId);
  scopedAccountIdRef.current = scopedAccountId;

  const fetchAccounts = async () => {
    try {
      const data = await api.getAccounts();
      setAccounts(data);
      setSelectedAccountId((prev) =>
        prev === 'all' || data.some((a) => a.id === prev) ? prev : 'all'
      );
    } catch (_) {}
  };

  const fetchGlobalStats = async (accId?: number) => {
    try {
      const targetId = accId !== undefined ? accId : scopedAccountId;
      const data = await api.getOverview(targetId);
      setStats(data);
      setBackendOnline(true);
    } catch (err) {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
    fetchGlobalStats(scopedAccountId);
    const interval = setInterval(() => {
      fetchGlobalStats(scopedAccountId);
    }, 10000);
    return () => clearInterval(interval);
  }, [selectedAccountId]);

  // Poll background sync telemetry (keeps running regardless of active tab)
  useEffect(() => {
    let isMounted = true;
    let wasActive = false;
    let lastInserted = -1;
    let lastUpdated = -1;
    let lastTickMs = 0;

    const pollSync = async () => {
      try {
        const res = await api.getActiveSync();
        if (!isMounted) return;
        const job = res.job || null;
        setActiveSyncJob(job);

        if (res.active && job) {
          wasActive = true;
          const now = Date.now();
          const changed =
            job.inserted_count !== lastInserted ||
            (job.updated_count || 0) !== lastUpdated;
          if (changed && now - lastTickMs >= 2000) {
            lastInserted = job.inserted_count;
            lastUpdated = job.updated_count || 0;
            lastTickMs = now;
            fetchGlobalStats(scopedAccountIdRef.current);
            setSyncRefreshTrigger((n) => n + 1);
          }
        } else if (wasActive) {
          wasActive = false;
          lastInserted = -1;
          lastUpdated = -1;
          fetchGlobalStats(scopedAccountIdRef.current);
          fetchAccounts();
          setSyncRefreshTrigger((n) => n + 1);
        }
      } catch (_) {}
    };

    pollSync();
    const interval = setInterval(pollSync, 800);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleStartSync = async (accountId: number, limit?: number) => {
    try {
      setGlobalError(null);
      const res = await api.startBackgroundSync(accountId, limit);
      setActiveSyncJob(res.job);
    } catch (err: any) {
      setGlobalError(err.message || 'Failed to start ingestion sync');
    }
  };

  const handleStopSync = async () => {
    try {
      await api.stopActiveSync();
      setActiveSyncJob((prev) => (prev ? { ...prev, status: 'stopping' } : null));
    } catch (err: any) {
      setGlobalError(err.message || 'Failed to stop ingestion sync');
    }
  };

  const handleSyncMailbox = async () => {
    try {
      setGlobalError(null);
      const accs = await api.getAccounts();
      setAccounts(accs);
      if (!accs || accs.length === 0) {
        setGlobalError('No mailbox accounts connected yet. Connect an account in Settings first.');
        setCurrentView('settings');
        return;
      }
      const activeAccs = accs.filter((a) => a.status !== 'paused');
      const scoped = scopedAccountId ? activeAccs.find((a) => a.id === scopedAccountId) : undefined;
      const targetAcc = scoped || activeAccs.find((a) => a.provider === 'imap' || a.provider === 'gmail') || activeAccs[0];
      if (!targetAcc) {
        setGlobalError('All connected accounts are currently paused. Re-enable an account in Settings.');
        setCurrentView('settings');
        return;
      }
      await handleStartSync(targetAcc.id, 100);
    } catch (err: any) {
      setGlobalError(err.message || 'Failed to start mailbox sync');
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchAccounts(), fetchGlobalStats()]);
    setRefreshing(false);
  };

  const handleQuickDemo = async () => {
    try {
      setGlobalError(null);
      await api.generateSynthetic({ message_count: 75 });
      await Promise.all([fetchAccounts(), fetchGlobalStats()]);
      setCurrentView('overview');
    } catch (err: any) {
      setGlobalError(err.message || 'Error generating demo data');
    }
  };

  // Keyboard navigation shortcuts (Alt+1 to Alt+9)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey) {
        const viewMap: Record<string, NavView> = {
          '1': 'overview',
          '2': 'graph',
          '3': 'messages',
          '4': 'senders',
          '5': 'cleanup',
          '6': 'timeline',
          '7': 'attachments',
          '8': 'insights',
          '9': 'settings',
        };
        if (viewMap[e.key]) {
          e.preventDefault();
          setCurrentView(viewMap[e.key]);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const viewTitles: Record<NavView, { title: string; subtitle: string }> = {
    overview: {
      title: 'Mailbox Intelligence Overview',
      subtitle: 'Local health, volume distribution, and storage telemetry',
    },
    graph: {
      title: 'Interactive Relationship Graph',
      subtitle: 'Multi-resolution domain clusters, sender networks, and thread flows',
    },
    messages: {
      title: 'Message Explorer & Full-Text Search',
      subtitle: 'Indexed messages with SQLite FTS5, filters, and sanitized previews',
    },
    senders: {
      title: 'Dedicated Sender Management',
      subtitle: 'Volume rankings, storage footprint, protection rules, and bulk cleanup',
    },
    cleanup: {
      title: 'Safe Cleanup Studio',
      subtitle: 'Exact target simulation, protection exclusions, and audit undo tracking',
    },
    timeline: {
      title: 'Email Time Machine',
      subtitle: 'Long-term volume trends, seasonal spikes, and sender lifecycles',
    },
    attachments: {
      title: 'Attachment Intelligence & Duplicate Detection',
      subtitle: 'Cryptographic hash grouping of redundant files across emails',
    },
    insights: {
      title: 'Explainable Insights & Recommendations',
      subtitle: 'Deterministic discovery of unreplied threads, zombie subscriptions, and storage dominators',
    },
    settings: {
      title: 'Application & Privacy Settings',
      subtitle: 'Accounts, local database controls, protection rules, and optional local AI',
    },
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-deep text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        onSelectView={setCurrentView}
        totalMessages={stats?.total_messages}
        storageMb={stats ? (stats.total_bytes / (1024 * 1024)).toFixed(1) : undefined}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <Header
          title={viewTitles[currentView].title}
          subtitle={viewTitles[currentView].subtitle}
          onRefresh={handleRefresh}
          onSyncMailbox={handleSyncMailbox}
          loading={refreshing}
          backendOnline={backendOnline}
          onQuickDemo={stats?.total_messages === 0 ? handleQuickDemo : undefined}
          activeSyncJob={activeSyncJob}
          onStopSync={handleStopSync}
          accounts={accounts}
          selectedAccountId={selectedAccountId}
          onSelectAccount={setSelectedAccountId}
        />

        {/* View Router */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {globalError && (
            <div className="px-4 py-2 bg-red-950/80 border-b border-red-700 text-red-200 text-xs font-mono flex items-center justify-between shrink-0 z-30">
              <span>{globalError}</span>
              <button
                onClick={() => setGlobalError(null)}
                className="text-red-300 hover:text-white px-2 font-bold"
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}

          {currentView === 'overview' && (
            <OverviewView
              accountId={scopedAccountId}
              accounts={accounts}
              refreshTrigger={syncRefreshTrigger}
              onNavigate={setCurrentView}
              onSyncMailbox={handleSyncMailbox}
              onDemoGenerated={async () => {
                await Promise.all([fetchAccounts(), fetchGlobalStats()]);
              }}
              isSyncActive={Boolean(
                activeSyncJob &&
                  (activeSyncJob.status === 'running' ||
                    activeSyncJob.status === 'starting' ||
                    activeSyncJob.status === 'stopping')
              )}
              onOpenSenderMessages={(addr) => {
                setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
            />
          )}

          {currentView === 'graph' && (
            <GraphView
              accountId={scopedAccountId}
              refreshTrigger={syncRefreshTrigger}
              onNavigateToMessages={(addr) => {
                if (addr) setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
              onNavigateToCleanup={(query) => {
                setCleanupInitialQuery(query);
                setCurrentView('cleanup');
              }}
            />
          )}

          {currentView === 'messages' && (
            <MessagesView
              accountId={scopedAccountId}
              refreshTrigger={syncRefreshTrigger}
              initialSender={messagesSenderFilter}
              onClearSenderFilter={() => setMessagesSenderFilter('')}
              onOpenCleanupWithQuery={(query) => {
                setCleanupInitialQuery(query);
                setCurrentView('cleanup');
              }}
            />
          )}

          {currentView === 'senders' && (
            <SendersView
              accountId={scopedAccountId}
              refreshTrigger={syncRefreshTrigger}
              onOpenMessagesWithSender={(addr) => {
                setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
            />
          )}

          {currentView === 'cleanup' && (
            <CleanupStudio
              accountId={scopedAccountId}
              initialQuery={cleanupInitialQuery}
              onClearInitialQuery={() => setCleanupInitialQuery(undefined)}
              onOperationsChanged={() => fetchGlobalStats(scopedAccountId)}
            />
          )}

          {currentView === 'timeline' && (
            <TimelineView
              accountId={scopedAccountId}
              refreshTrigger={syncRefreshTrigger}
              onOpenSenderMessages={(addr) => {
                setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
            />
          )}

          {currentView === 'attachments' && (
            <AttachmentsView accountId={scopedAccountId} refreshTrigger={syncRefreshTrigger} />
          )}

          {currentView === 'insights' && (
            <InsightsView
              accountId={scopedAccountId}
              refreshTrigger={syncRefreshTrigger}
              onOpenMessages={(addr) => {
                if (addr) setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
              onOpenAttachments={() => setCurrentView('attachments')}
              onOpenCleanup={(query) => {
                setCleanupInitialQuery(query);
                setCurrentView('cleanup');
              }}
            />
          )}

          {currentView === 'settings' && (
            <SettingsView
              activeSyncJob={activeSyncJob}
              onStartSync={handleStartSync}
              onStopSync={handleStopSync}
              onAccountsChanged={() => {
                fetchAccounts();
                fetchGlobalStats(scopedAccountId);
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
};
export default App;
