import React, { useState, useEffect } from 'react';
import { Clock, Calendar, BarChart3, TrendingUp, Users, ArrowRight } from 'lucide-react';
import { api } from '../../api/client';
import { Button } from '../../components/Button';

interface TimelineViewProps {
  onOpenSenderMessages?: (senderAddress: string) => void;
}

export const TimelineView: React.FC<TimelineViewProps> = ({ onOpenSenderMessages }) => {
  const [groupBy, setGroupBy] = useState<'year' | 'month' | 'day'>('month');
  const [volumeData, setVolumeData] = useState<any[]>([]);
  const [senderTimeline, setSenderTimeline] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchTimelineData = async () => {
    setLoading(true);
    try {
      const [vol, senders] = await Promise.all([
        api.getTimelineVolume(groupBy),
        api.getTimelineSenders(15),
      ]);
      setVolumeData(vol);
      setSenderTimeline(senders);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTimelineData();
  }, [groupBy]);

  const maxVolume = Math.max(...volumeData.map((d) => d.message_count), 1);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-bg-deep select-none">
      {/* Header and Interval Selection */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-bg-surface p-4 rounded-lg border border-border-subtle shadow-sm">
        <div>
          <h2 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
            <Clock className="w-4 h-4 text-brand-light" />
            Email Time Machine & History
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Analyze historical communication volume, sender activity lifecycles, and storage growth over time.
          </p>
        </div>

        <div className="flex items-center gap-1 bg-bg-deep p-0.5 rounded border border-border-muted text-xs">
          <button
            onClick={() => setGroupBy('month')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              groupBy === 'month' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setGroupBy('year')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              groupBy === 'year' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Yearly
          </button>
        </div>
      </div>

      {/* Volume Histogram Chart */}
      <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            Incoming Message Volume Over Time
          </h3>
          <span className="text-xs font-mono text-slate-400">{volumeData.length} periods observed</span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs font-mono text-slate-400">
            Calculating historical volume metrics...
          </div>
        ) : volumeData.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 font-sans">
            No historical timeline data recorded.
          </div>
        ) : (
          <div className="space-y-2 pt-2">
            <div className="h-48 flex items-end gap-1.5 border-b border-border-subtle pb-2 px-2 overflow-x-auto">
              {volumeData.map((d) => {
                const heightPct = Math.max(6, (d.message_count / maxVolume) * 100);
                return (
                  <div
                    key={d.period}
                    className="flex-1 min-w-[28px] max-w-[50px] flex flex-col items-center gap-1 group relative cursor-pointer"
                  >
                    {/* Tooltip on hover */}
                    <div className="absolute -top-12 bg-slate-900 border border-border-muted px-2 py-1 rounded text-[10px] font-mono text-slate-200 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none shadow-xl">
                      {d.period}: {d.message_count} msgs ({(d.total_bytes / 1024).toFixed(0)} KB)
                    </div>

                    <div
                      className="w-full bg-brand/70 hover:bg-brand rounded-t transition-all"
                      style={{ height: `${heightPct}%` }}
                    />
                    <span className="text-[10px] font-mono text-slate-500 truncate w-full text-center">
                      {d.period.slice(2)}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-[11px] font-mono text-slate-500 px-2">
              <span>Earliest: {volumeData[0]?.period}</span>
              <span>Latest: {volumeData[volumeData.length - 1]?.period}</span>
            </div>
          </div>
        )}
      </div>

      {/* Sender Lifecycles Table */}
      <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-purple-400" />
          Sender Activity Lifecycles (First Observed vs Recent)
        </h3>

        <div className="border border-border-subtle rounded divide-y divide-border-subtle overflow-hidden">
          {senderTimeline.map((s) => (
            <div
              key={s.id}
              onClick={() => onOpenSenderMessages && onOpenSenderMessages(s.address)}
              className="p-3.5 flex items-center justify-between hover:bg-bg-elevated cursor-pointer transition-colors text-xs"
            >
              <div className="truncate max-w-sm font-sans">
                <div className="font-semibold text-slate-200 truncate">{s.display_name}</div>
                <div className="text-[11px] font-mono text-slate-400 truncate">{s.address}</div>
              </div>

              <div className="flex items-center gap-6 font-mono text-[11px]">
                <div>
                  <span className="text-slate-500">First Seen: </span>
                  <span className="text-slate-300">{s.first_seen?.slice(0, 10)}</span>
                </div>
                <div>
                  <span className="text-slate-500">Last Seen: </span>
                  <span className="text-slate-300">{s.last_seen?.slice(0, 10)}</span>
                </div>
                <div className="text-right w-24">
                  <span className="text-slate-100 font-bold">{s.message_count} msgs</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
