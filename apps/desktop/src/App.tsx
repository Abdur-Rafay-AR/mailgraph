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
import { OverviewStats, QueryAST } from './types/api';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('overview');
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Cross-view state handoffs
  const [messagesSenderFilter, setMessagesSenderFilter] = useState<string>('');
  const [cleanupInitialQuery, setCleanupInitialQuery] = useState<QueryAST | undefined>(undefined);

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
          loading={refreshing}
          backendOnline={backendOnline}
          onQuickDemo={stats?.total_messages === 0 ? handleQuickDemo : undefined}
        />

        {/* View Router */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {currentView === 'overview' && (
            <OverviewView
              onNavigate={setCurrentView}
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

          {currentView === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  );
};
export default App;
