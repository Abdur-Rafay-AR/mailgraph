import React, { useState, useEffect } from 'react';
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
import { OverviewStats, QueryAST, SyncJob } from './types/api';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('overview');
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Cross-view state handoffs
  const [messagesSenderFilter, setMessagesSenderFilter] = useState<string>('');
  const [cleanupInitialQuery, setCleanupInitialQuery] = useState<QueryAST | undefined>(undefined);

  // Global background ingestion state
  const [activeSyncJob, setActiveSyncJob] = useState<SyncJob | null>(null);

  const fetchGlobalStats = async () => {
    try {
      const data = await api.getOverview();
      setStats(data);
      setBackendOnline(true);
    } catch (err) {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    fetchGlobalStats();
    const interval = setInterval(fetchGlobalStats, 10000);
    return () => clearInterval(interval);
  }, []);

  // Poll background sync telemetry (keeps running regardless of active tab)
  useEffect(() => {
    let isMounted = true;
    const pollSync = async () => {
      try {
        const res = await api.getActiveSync();
        if (!isMounted) return;
        if (res.active && res.job) {
          setActiveSyncJob(res.job);
        } else {
          setActiveSyncJob((prev) => {
            if (prev && (prev.status === 'running' || prev.status === 'stopping')) {
              // Sync just finished or stopped: refresh global stats
              fetchGlobalStats();
            }
            return res.job || null;
          });
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
      const res = await api.startBackgroundSync(accountId, limit);
      setActiveSyncJob(res.job);
    } catch (err: any) {
      alert(err.message || 'Failed to start ingestion sync');
    }
  };

  const handleStopSync = async () => {
    try {
      await api.stopActiveSync();
      setActiveSyncJob((prev) => (prev ? { ...prev, status: 'stopping' } : null));
    } catch (err: any) {
      alert(err.message || 'Failed to stop ingestion sync');
    }
  };

  const handleSyncMailbox = async () => {
    try {
      const accounts = await api.getAccounts();
      if (!accounts || accounts.length === 0) {
        alert('No mailbox accounts connected yet. Please connect an account in Settings first.');
        setCurrentView('settings');
        return;
      }
      const targetAcc = accounts.find((a) => a.provider === 'imap' || a.provider === 'gmail') || accounts[0];
      await handleStartSync(targetAcc.id, 100);
    } catch (err: any) {
      alert(err.message || 'Failed to start mailbox sync');
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchGlobalStats();
    setRefreshing(false);
  };

  const handleQuickDemo = async () => {
    try {
      await api.generateSynthetic({ message_count: 75 });
      await fetchGlobalStats();
      setCurrentView('overview');
    } catch (err: any) {
      alert(err.message || 'Error generating demo data');
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
        />

        {/* View Router */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {currentView === 'overview' && (
            <OverviewView
              onNavigate={setCurrentView}
              onSyncMailbox={handleSyncMailbox}
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
              initialSender={messagesSenderFilter}
              onOpenCleanupWithQuery={(query) => {
                setCleanupInitialQuery(query);
                setCurrentView('cleanup');
              }}
            />
          )}

          {currentView === 'senders' && (
            <SendersView
              onOpenMessagesWithSender={(addr) => {
                setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
            />
          )}

          {currentView === 'cleanup' && (
            <CleanupStudio initialQuery={cleanupInitialQuery} />
          )}

          {currentView === 'timeline' && (
            <TimelineView
              onOpenSenderMessages={(addr) => {
                setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
            />
          )}

          {currentView === 'attachments' && <AttachmentsView />}

          {currentView === 'insights' && (
            <InsightsView
              onOpenMessages={(addr) => {
                if (addr) setMessagesSenderFilter(addr);
                setCurrentView('messages');
              }}
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
            />
          )}
        </main>
      </div>
    </div>
  );
};
export default App;
