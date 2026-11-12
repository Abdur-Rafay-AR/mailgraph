import React, { useState, useEffect } from 'react';
import { Lightbulb, AlertTriangle, ShieldCheck, HardDrive, Clock, Mail, ExternalLink, Check, Trash2 } from 'lucide-react';
import { api } from '../../api/client';
import { Insight, QueryAST } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

interface InsightsViewProps {
  onOpenMessages?: (senderAddress?: string) => void;
  onOpenCleanup?: (query: QueryAST) => void;
}

export const InsightsView: React.FC<InsightsViewProps> = ({
  onOpenMessages,
  onOpenCleanup,
}) => {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchInsights = async () => {
    setLoading(true);
    try {
      const data = await api.getInsights();
      setInsights(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  const handleDismiss = async (id: number) => {
    try {
      await api.dismissInsight(id);
      setInsights((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'storage_dominator':
        return <HardDrive className="w-5 h-5 text-amber-400" />;
      case 'zombie_subscription':
        return <Mail className="w-5 h-5 text-purple-400" />;
      case 'large_attachments':
        return <AlertTriangle className="w-5 h-5 text-red-400" />;
      case 'unreplied_thread':
        return <Clock className="w-5 h-5 text-blue-400" />;
      default:
        return <Lightbulb className="w-5 h-5 text-brand-light" />;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-bg-deep select-none">
      {/* Header */}
      <div className="bg-bg-surface p-4 rounded-lg border border-border-subtle shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            Explainable Mailbox Insights & Recommendations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Every insight explains its supporting telemetry and evidence. MailGraph never modifies mailbox state without explicit user approval.
          </p>
        </div>
        <Button size="xs" variant="ghost" onClick={fetchInsights} loading={loading}>
          Re-evaluate
        </Button>
      </div>

      {/* Insights Grid */}
      <div className="space-y-4">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-400 font-mono">
            Evaluating mailbox patterns against local heuristics...
          </div>
        ) : insights.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 font-sans">
            No active anomalies or cleanup recommendations detected.
          </div>
        ) : (
          insights.map((ins) => (
            <div
              key={ins.id}
              className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-3.5 hover:border-brand/40 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded bg-bg-deep border border-border-subtle shrink-0">
                    {getInsightIcon(ins.insight_type)}
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-slate-100">{ins.title}</h4>
                    <p className="text-xs text-slate-300 mt-1 leading-relaxed max-w-2xl font-sans">
                      {ins.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400">
                    Confidence: {(ins.confidence * 100).toFixed(0)}%
                  </span>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => handleDismiss(ins.id)}
                    title="Dismiss recommendation"
                  >
                    Dismiss
                  </Button>
                </div>
              </div>

              {/* Evidence Inspector */}
              {ins.evidence && Object.keys(ins.evidence).length > 0 && (
                <div className="p-3 bg-bg-deep rounded border border-border-subtle flex flex-wrap items-center gap-4 text-xs font-mono">
                  <span className="text-slate-500 text-[11px] uppercase tracking-wider">
                    Supporting Evidence:
                  </span>
                  {Object.entries(ins.evidence).map(([key, val]) => (
                    <div key={key} className="flex items-center gap-1.5 text-slate-300 text-[11px]">
                      <span className="text-slate-500">{key}:</span>
                      <span className="font-semibold">
                        {typeof val === 'number' && key.includes('bytes')
                          ? `${(val / (1024 * 1024)).toFixed(2)} MB`
                          : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2">
                {ins.evidence?.sender_address && onOpenMessages && (
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => onOpenMessages(ins.evidence.sender_address)}
                    icon={<ExternalLink className="w-3.5 h-3.5" />}
                  >
                    Inspect Messages
                  </Button>
                )}

                {ins.evidence?.sender_address && onOpenCleanup && (
                  <Button
                    size="xs"
                    variant="danger"
                    onClick={() =>
                      onOpenCleanup({
                        all: [{ field: 'sender_address', op: 'eq', value: ins.evidence.sender_address }],
                        exclude_protected: true,
                      })
                    }
                    icon={<Trash2 className="w-3.5 h-3.5" />}
                  >
                    Review for Cleanup
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
