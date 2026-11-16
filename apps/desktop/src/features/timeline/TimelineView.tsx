import React, { useState, useEffect, useMemo } from 'react';
import {
  Clock,
  Calendar,
  BarChart3,
  TrendingUp,
  Users,
  HardDrive,
  Activity,
  Flame,
  ArrowRight,
  Shield,
  Layers,
  Database
} from 'lucide-react';
import { api } from '../../api/client';
import { Button } from '../../components/Button';

interface TimelineViewProps {
  accountId?: number;
  onOpenSenderMessages?: (senderAddress: string) => void;
}

export const TimelineView: React.FC<TimelineViewProps> = ({ accountId, onOpenSenderMessages }) => {
  const [groupBy, setGroupBy] = useState<'year' | 'month' | 'day'>('month');
  const [metricMode, setMetricMode] = useState<'volume' | 'storage'>('volume');
  const [volumeData, setVolumeData] = useState<any[]>([]);
  const [senderTimeline, setSenderTimeline] = useState<any[]>([]);
  const [cadenceData, setCadenceData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchTimelineData = async () => {
    setLoading(true);
    try {
      const [vol, senders, cadence] = await Promise.all([
        api.getTimelineVolume(groupBy, groupBy === 'day' ? 30 : undefined, accountId),
        api.getTimelineSenders(15, accountId),
        api.getTimelineCadence(accountId),
      ]);
      setVolumeData(vol || []);
      setSenderTimeline(senders || []);
      setCadenceData(cadence || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTimelineData();
  }, [groupBy, accountId]);

  // Derived KPI metrics
  const totalVolume = useMemo(() => {
    return volumeData.reduce((acc, d) => acc + (d.message_count || 0), 0);
  }, [volumeData]);

  const totalBytes = useMemo(() => {
    return volumeData.reduce((acc, d) => acc + (d.total_bytes || 0), 0);
  }, [volumeData]);

  const peakPeriod = useMemo(() => {
    if (!volumeData || volumeData.length === 0) return null;
    return volumeData.reduce((max, d) => (d.message_count > max.message_count ? d : max), volumeData[0]);
  }, [volumeData]);

  const earliestPeriod = volumeData[0]?.period || null;
  const latestPeriod = volumeData[volumeData.length - 1]?.period || null;

  // Max value for scaling chart bars
  const maxValue = useMemo(() => {
    if (metricMode === 'volume') {
      return Math.max(...volumeData.map((d) => d.message_count || 0), 1);
    }
    return Math.max(...volumeData.map((d) => (d.total_bytes || 0) / (1024 * 1024)), 0.1);
  }, [volumeData, metricMode]);

  // Calculate global timestamp min and max for Gantt timeline
  const globalTimelineSpan = useMemo(() => {
    if (!senderTimeline || senderTimeline.length === 0) {
      return { min: Date.now() - 365 * 86400000, max: Date.now() };
    }
    const timestamps = senderTimeline.flatMap((s) => [
      s.first_seen ? new Date(s.first_seen).getTime() : Date.now(),
      s.last_seen ? new Date(s.last_seen).getTime() : Date.now(),
    ]);
    const min = Math.min(...timestamps);
    const max = Math.max(...timestamps);
    return { min, max: Math.max(max, min + 86400000) };
  }, [senderTimeline]);

  // Max cadence count for day-of-week bar
  const maxCadence = useMemo(() => {
    return Math.max(...cadenceData.map((c) => c.count || 0), 1);
  }, [cadenceData]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-bg-deep select-none">
      {/* Header and Interval & Metric Selection Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-bg-surface p-4 border border-border-subtle rounded-none shadow-sm">
        <div>
          <h2 className="text-sm font-bold text-white tracking-wider uppercase font-sans flex items-center gap-2">
            <Clock className="w-4 h-4 text-brand" />
            Email Time Machine & Volume History
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Temporal intake distribution, storage footprint expansion, and sender activity lifecycles.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Metric Toggle: Volume vs Storage */}
          <div className="flex items-center bg-bg-deep p-0.5 border border-border-muted rounded-none text-xs font-mono">
            <button
              onClick={() => setMetricMode('volume')}
              className={`px-2.5 py-1 transition-colors ${
                metricMode === 'volume'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Messages
            </button>
            <button
              onClick={() => setMetricMode('storage')}
              className={`px-2.5 py-1 transition-colors ${
                metricMode === 'storage'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Storage (MB)
            </button>
          </div>

          {/* Granularity Toggle: Day vs Month vs Year */}
          <div className="flex items-center bg-bg-deep p-0.5 border border-border-muted rounded-none text-xs font-mono">
            <button
              onClick={() => setGroupBy('day')}
              className={`px-2.5 py-1 transition-colors ${
                groupBy === 'day'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Recent 30 Days daily cadence"
            >
              Daily (30d)
            </button>
            <button
              onClick={() => setGroupBy('month')}
              className={`px-2.5 py-1 transition-colors ${
                groupBy === 'month'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Monthly aggregation across entire history"
            >
              Monthly
            </button>
            <button
              onClick={() => setGroupBy('year')}
              className={`px-2.5 py-1 transition-colors ${
                groupBy === 'year'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Year-over-year volume comparison"
            >
              Yearly
            </button>
          </div>
        </div>
      </div>

      {/* 4 Primary KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Observed Timespan */}
        <div className="p-4 bg-bg-surface border border-border-subtle rounded-none font-mono">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>OBSERVED HORIZON</span>
            <Calendar className="w-4 h-4 text-brand" />
          </div>
          <div className="text-lg font-bold text-white tracking-tight">
            {earliestPeriod && latestPeriod ? (
              `${earliestPeriod} → ${latestPeriod}`
            ) : (
              'No Data'
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {volumeData.length} periods observed ({groupBy})
          </div>
        </div>

        {/* Card 2: Peak Inflow Period */}
        <div className="p-4 bg-bg-surface border border-border-subtle rounded-none font-mono">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>PEAK INFLOW SPIKE</span>
            <Flame className="w-4 h-4 text-brand" />
          </div>
          <div className="text-lg font-bold text-white tracking-tight truncate">
            {peakPeriod ? peakPeriod.period : 'None'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {peakPeriod ? `${peakPeriod.message_count.toLocaleString()} msgs (${((peakPeriod.total_bytes || 0) / (1024 * 1024)).toFixed(1)} MB)` : '0 msgs'}
          </div>
        </div>

        {/* Card 3: Inflow Velocity */}
        <div className="p-4 bg-bg-surface border border-border-subtle rounded-none font-mono">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>INTAKE VELOCITY</span>
            <Activity className="w-4 h-4 text-brand" />
          </div>
          <div className="text-lg font-bold text-white tracking-tight">
            {volumeData.length > 0
              ? `${Math.round(totalVolume / volumeData.length)}`
              : '0'}{' '}
            <span className="text-xs font-normal text-slate-400">msgs/{groupBy}</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {totalVolume.toLocaleString()} total messages in view
          </div>
        </div>

        {/* Card 4: Storage Footprint */}
        <div className="p-4 bg-bg-surface border border-border-subtle rounded-none font-mono">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>STORAGE TRAJECTORY</span>
            <HardDrive className="w-4 h-4 text-brand" />
          </div>
          <div className="text-lg font-bold text-white tracking-tight">
            {(totalBytes / (1024 * 1024)).toFixed(1)}{' '}
            <span className="text-xs font-normal text-slate-400">MB Total</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            ~{volumeData.length > 0 ? ((totalBytes / volumeData.length) / 1024).toFixed(0) : 0} KB per {groupBy}
          </div>
        </div>
      </div>

      {/* Main Volume Histogram with Gridlines & Y-Axis Scale */}
      <div className="bg-bg-surface border border-border-subtle p-5 rounded-none shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white tracking-wider uppercase font-sans flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-brand" />
            {metricMode === 'volume'
              ? 'Message Volume Distribution Over Time'
              : 'Storage Footprint Expansion (MB) Over Time'}
          </h3>
          <span className="text-xs font-mono text-slate-400">
            {metricMode === 'volume' ? 'Values in message count' : 'Values in megabytes'}
          </span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-xs font-mono text-slate-400">
            Analyzing historical mailbox metrics and time intervals...
          </div>
        ) : volumeData.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <div className="text-xs font-mono text-slate-400">No historical timestamp data observed.</div>
            <div className="text-[11px] text-slate-500 font-mono">
              Connect a mailbox or import an archive to explore long-term trends.
            </div>
          </div>
        ) : (
          <div className="pt-2">
            {/* Chart Area with Gridlines and Y-Axis */}
            <div className="relative h-60 flex border border-border-subtle bg-bg-deep p-3">
              {/* Y-Axis Reference Scale */}
              <div className="w-12 h-full flex flex-col justify-between text-[10px] font-mono text-slate-500 pr-2 border-r border-border-subtle select-none pb-5">
                <span>{metricMode === 'volume' ? maxValue : maxValue.toFixed(1)}</span>
                <span>{metricMode === 'volume' ? Math.round(maxValue * 0.75) : (maxValue * 0.75).toFixed(1)}</span>
                <span>{metricMode === 'volume' ? Math.round(maxValue * 0.5) : (maxValue * 0.5).toFixed(1)}</span>
                <span>{metricMode === 'volume' ? Math.round(maxValue * 0.25) : (maxValue * 0.25).toFixed(1)}</span>
                <span>0</span>
              </div>

              {/* Chart Bars with Horizontal Gridlines */}
              <div className="flex-1 relative flex items-end gap-2 px-3 overflow-x-auto pb-5">
                {/* 4 Horizontal Dashed Gridlines */}
                <div className="absolute inset-x-0 top-0 border-b border-border-subtle/50 pointer-events-none" />
                <div className="absolute inset-x-0 top-1/4 border-b border-border-subtle/40 pointer-events-none" />
                <div className="absolute inset-x-0 top-2/4 border-b border-border-subtle/40 pointer-events-none" />
                <div className="absolute inset-x-0 top-3/4 border-b border-border-subtle/40 pointer-events-none" />
                <div className="absolute inset-x-0 bottom-5 border-b border-border-subtle pointer-events-none" />

                {volumeData.map((d) => {
                  const val = metricMode === 'volume' ? d.message_count : d.total_bytes / (1024 * 1024);
                  const heightPct = Math.max(4, Math.min(100, (val / maxValue) * 100));

                  return (
                    <div
                      key={d.period}
                      className="flex-1 min-w-[24px] max-w-[64px] flex flex-col items-center gap-1 group relative cursor-pointer z-10"
                    >
                      {/* Interactive Hover HUD Tooltip */}
                      <div className="absolute -top-16 bg-[#0A0A0A] border border-border-muted px-2.5 py-1.5 rounded-none text-[10px] font-mono text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-30 pointer-events-none shadow-2xl">
                        <div className="font-bold text-brand">{d.period}</div>
                        <div>
                          {d.message_count.toLocaleString()} messages • {((d.total_bytes || 0) / 1024).toFixed(0)} KB
                        </div>
                        {d.unread_count > 0 && (
                          <div className="text-amber-400 text-[9px]">{d.unread_count} unread in period</div>
                        )}
                      </div>

                      {/* Bar Pillar */}
                      <div
                        className="w-full bg-brand/80 hover:bg-brand rounded-none transition-all duration-200 border-t border-brand"
                        style={{ height: `${heightPct}%` }}
                      />

                      {/* Period Label */}
                      <span className="text-[10px] font-mono text-slate-400 truncate w-full text-center mt-1">
                        {groupBy === 'day' ? d.period.slice(5) : groupBy === 'month' ? d.period.slice(2) : d.period}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Bottom Horizon Footnote */}
            <div className="flex justify-between items-center text-[11px] font-mono text-slate-400 pt-2 px-1">
              <span>Earliest: <strong className="text-white">{earliestPeriod}</strong></span>
              <span>Observed: <strong className="text-white">{volumeData.length} {groupBy}s</strong></span>
              <span>Latest: <strong className="text-white">{latestPeriod}</strong></span>
            </div>
          </div>
        )}
      </div>

      {/* Two Column Layout: Day of Week Cadence + Sender Lifecycle Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: Day of Week Cadence Matrix */}
        <div className="bg-bg-surface border border-border-subtle p-5 rounded-none shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-bold text-white tracking-wider uppercase font-sans flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand" />
              Weekly Intake Rhythm
            </h3>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">
              Communication distribution by day of the week.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            {cadenceData.map((c) => {
              const pct = Math.max(5, (c.count / maxCadence) * 100);
              const isPeak = c.count === maxCadence;

              return (
                <div key={c.day} className="space-y-1 font-mono text-xs">
                  <div className="flex justify-between text-[11px]">
                    <span className={isPeak ? 'font-bold text-brand' : 'text-slate-300'}>
                      {c.day}
                    </span>
                    <span className="text-slate-400 tabular-nums">
                      {c.count.toLocaleString()} msgs
                    </span>
                  </div>
                  <div className="w-full bg-bg-deep border border-border-subtle h-2 overflow-hidden rounded-none">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isPeak ? 'bg-brand' : 'bg-slate-500'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Column 2: Visual Sender Lifecycles (Gantt-Style Span Bars) */}
        <div className="lg:col-span-2 bg-bg-surface border border-border-subtle p-5 rounded-none shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white tracking-wider uppercase font-sans flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand" />
                Correspondent Activity Lifecycles
              </h3>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                First observed vs latest active window plotted across your complete mailbox horizon.
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">Top {senderTimeline.length} senders</span>
          </div>

          <div className="border border-border-subtle rounded-none divide-y divide-border-subtle overflow-hidden font-mono text-xs">
            {senderTimeline.map((s) => {
              const startTs = s.first_seen ? new Date(s.first_seen).getTime() : globalTimelineSpan.min;
              const endTs = s.last_seen ? new Date(s.last_seen).getTime() : globalTimelineSpan.max;
              const spanDuration = globalTimelineSpan.max - globalTimelineSpan.min;

              const leftPct = Math.max(0, Math.min(95, ((startTs - globalTimelineSpan.min) / spanDuration) * 100));
              const rightPct = Math.max(0, Math.min(100, ((endTs - globalTimelineSpan.min) / spanDuration) * 100));
              const widthPct = Math.max(3, rightPct - leftPct);

              // Activity classification: active within 30 days or dormant
              const daysSinceLast = (Date.now() - endTs) / 86400000;
              const statusTag = daysSinceLast <= 30 ? 'ACTIVE' : daysSinceLast >= 180 ? 'DORMANT' : 'LAPSED';

              return (
                <div
                  key={s.id}
                  onClick={() => onOpenSenderMessages && onOpenSenderMessages(s.address)}
                  className="p-3.5 hover:bg-bg-elevated cursor-pointer transition-colors space-y-2 group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 truncate max-w-md">
                      <span className="font-bold text-white uppercase truncate font-sans">
                        {s.display_name}
                      </span>
                      <span className="text-[10px] text-slate-400 truncate">
                        @{s.domain || s.address.split('@')[1]}
                      </span>
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded-none border uppercase ${
                          statusTag === 'ACTIVE'
                            ? 'bg-emerald-950/40 border-emerald-800 text-emerald-400'
                            : statusTag === 'DORMANT'
                            ? 'bg-zinc-900 border-zinc-700 text-slate-400'
                            : 'bg-amber-950/40 border-amber-800 text-amber-400'
                        }`}
                      >
                        {statusTag}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-[11px] tabular-nums">
                      <span className="text-white font-bold">{s.message_count.toLocaleString()} msgs</span>
                      <span className="text-slate-500">
                        {s.total_bytes > 1024 * 1024
                          ? `${(s.total_bytes / (1024 * 1024)).toFixed(1)} MB`
                          : `${Math.round(s.total_bytes / 1024)} KB`}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand transition-colors" />
                    </div>
                  </div>

                  {/* Horizontal Gantt Span Track */}
                  <div className="space-y-1">
                    <div className="relative w-full bg-bg-deep border border-border-subtle h-2 overflow-hidden rounded-none">
                      <div
                        className="absolute h-full bg-brand group-hover:bg-brand/90 transition-all rounded-none"
                        style={{
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                        }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-slate-500 tabular-nums">
                      <span>First: {s.first_seen?.slice(0, 10)}</span>
                      <span>Last: {s.last_seen?.slice(0, 10)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
