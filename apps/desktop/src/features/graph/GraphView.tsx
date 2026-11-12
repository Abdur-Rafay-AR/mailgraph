import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, EventObject } from 'cytoscape';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  SlidersHorizontal,
  ExternalLink,
  Shield,
  Trash2,
  Users
} from 'lucide-react';
import { api } from '../../api/client';
import { GraphNodeData, QueryAST } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

interface GraphViewProps {
  onNavigateToMessages?: (senderAddress?: string) => void;
  onNavigateToCleanup?: (query: QueryAST) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({
  onNavigateToMessages,
  onNavigateToCleanup,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [level, setLevel] = useState<'domain' | 'sender' | 'thread'>('domain');
  const [selectedDomain, setSelectedDomain] = useState<string>('');
  const [sizeMetric, setSizeMetric] = useState<'count' | 'size'>('count');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  // Selected node inspection panel
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);

  const fetchAndRenderGraph = async () => {
    setLoading(true);
    try {
      const data = await api.getGraph({
        level,
        selected_domain: selectedDomain || undefined,
        category: categoryFilter || undefined,
      });

      if (!containerRef.current) return;

      // Clean existing Cytoscape instance
      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const cy = cytoscape({
        container: containerRef.current,
        elements: data.elements,
        boxSelectionEnabled: false,
        autounselectify: false,
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)',
              color: '#f8fafc',
              'font-size': '11px',
              'font-family': 'JetBrains Mono, monospace',
              'text-valign': 'bottom',
              'text-margin-y': 6,
              'background-color': 'data(color)',
              'border-width': 2,
              'border-color': '#475569',
              width: (ele: any) => {
                const count = ele.data('message_count') || 1;
                const base = Math.min(65, Math.max(22, Math.log2(count + 1) * 8));
                return `${base}px`;
              },
              height: (ele: any) => {
                const count = ele.data('message_count') || 1;
                const base = Math.min(65, Math.max(22, Math.log2(count + 1) * 8));
                return `${base}px`;
              },
              'transition-property': 'background-color, border-color, width, height',
              'transition-duration': 0.15,
            },
          },
          {
            selector: 'node[node_type = "hub"]',
            style: {
              'background-color': '#9061f9',
              'border-color': '#c084fc',
              'border-width': 3,
              width: '45px',
              height: '45px',
              'font-weight': 'bold',
            },
          },
          {
            selector: 'node:selected',
            style: {
              'border-color': '#c084fc',
              'border-width': 4,
              'underlay-color': '#9061f9',
              'underlay-padding': 4,
              'underlay-opacity': 0.4,
            },
          },
          {
            selector: 'edge',
            style: {
              width: (ele: any) => {
                const w = ele.data('weight') || 1;
                return `${Math.min(4, Math.max(1, Math.log2(w + 1)))}px`;
              },
              'line-color': '#3d2b6e',
              'curve-style': 'bezier',
              opacity: 0.6,
            },
          },
          {
            selector: 'edge:selected',
            style: {
              'line-color': '#c084fc',
              opacity: 1,
            },
          },
        ],
        layout: {
          name: level === 'domain' ? 'concentric' : 'cose',
          animate: true,
          animationDuration: 400,
          padding: 30,
        },
      });

      // Node selection listener
      cy.on('tap', 'node', (evt: EventObject) => {
        const node = evt.target;
        setSelectedNode(node.data());
      });

      // Background click to deselect
      cy.on('tap', (evt: EventObject) => {
        if (evt.target === cy) {
          setSelectedNode(null);
        }
      });

      // Double click to drill down into domain
      cy.on('dbltap', 'node[node_type = "domain"]', (evt: EventObject) => {
        const domain = evt.target.data('domain');
        if (domain) {
          setSelectedDomain(domain);
          setLevel('sender');
        }
      });

      cyRef.current = cy;
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAndRenderGraph();
  }, [level, selectedDomain, categoryFilter]);

  // Layout resets and zoom
  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit();
  const handleResetLayout = () => {
    cyRef.current?.layout({ name: level === 'domain' ? 'concentric' : 'cose', animate: true }).run();
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden relative select-none">
      {/* Top Filter and Level Switcher */}
      <div className="p-3 bg-bg-surface border-b border-border-subtle flex flex-wrap items-center justify-between gap-3 z-10">
        <div className="flex items-center gap-2">
          {/* Level Switcher */}
          <div className="flex items-center bg-bg-deep p-0.5 rounded border border-border-muted text-xs">
            <button
              onClick={() => {
                setSelectedDomain('');
                setLevel('domain');
              }}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                level === 'domain' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Domain Clusters
            </button>
            <button
              onClick={() => setLevel('sender')}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                level === 'sender' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sender Network
            </button>
          </div>

          {selectedDomain && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand/15 border border-brand/30 text-brand-light text-xs font-mono">
              Domain: {selectedDomain}
              <button
                onClick={() => {
                  setSelectedDomain('');
                  setLevel('domain');
                }}
                className="hover:text-white font-bold ml-1"
              >
                ×
              </button>
            </span>
          )}
        </div>

        {/* Category & Controls */}
        <div className="flex items-center gap-2">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-bg-deep border border-border-muted rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
          >
            <option value="">All Categories</option>
            <option value="important">Important</option>
            <option value="personal">Personal</option>
            <option value="work">Work</option>
            <option value="newsletter">Newsletters</option>
            <option value="receipt_invoice">Receipts</option>
            <option value="security">Security</option>
            <option value="promotional">Promotional</option>
          </select>

          <Button size="xs" variant="outline" onClick={handleResetLayout} title="Reset layout calculation">
            Reset Layout
          </Button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 relative w-full h-full">
        {loading && (
          <div className="absolute inset-0 bg-bg-deep/60 backdrop-blur-xs flex items-center justify-center z-20 text-xs font-mono text-slate-300">
            Rendering relationship graph...
          </div>
        )}

        <div ref={containerRef} className="w-full h-full bg-slate-950" />

        {/* Floating Zoom & Fit Controls */}
        <div className="absolute bottom-4 left-4 flex flex-col gap-1 bg-bg-surface/90 border border-border-muted rounded p-1 shadow-xl z-20">
          <button
            onClick={handleZoomIn}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 rounded"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 rounded"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFit}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 rounded"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Node Detail Side Panel */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-80 bg-bg-surface/95 border border-border-muted shadow-2xl rounded-lg p-4 space-y-3 z-20 backdrop-blur-md animate-fadeIn text-xs">
            <div className="flex items-start justify-between border-b border-border-subtle pb-2">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  {selectedNode.node_type} Node
                </span>
                <h4 className="text-sm font-semibold text-slate-100 truncate max-w-[200px]">
                  {selectedNode.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ×
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
              <div className="p-2 bg-bg-deep rounded border border-border-subtle">
                <div className="text-slate-400">Total Volume</div>
                <div className="text-sm font-bold text-slate-200">
                  {selectedNode.message_count?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2 bg-bg-deep rounded border border-border-subtle">
                <div className="text-slate-400">Storage</div>
                <div className="text-sm font-bold text-slate-200">
                  {selectedNode.total_bytes
                    ? `${(selectedNode.total_bytes / (1024 * 1024)).toFixed(2)} MB`
                    : 'N/A'}
                </div>
              </div>
            </div>

            {selectedNode.unread_count !== undefined && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px]">
                <span>Unread Messages:</span>
                <span className="text-amber-400 font-semibold">{selectedNode.unread_count}</span>
              </div>
            )}

            {selectedNode.category && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px]">
                <span>Dominant Category:</span>
                <Badge label={selectedNode.category} color={selectedNode.color} />
              </div>
            )}

            {/* Quick Drilldown Buttons */}
            <div className="pt-2 border-t border-border-subtle space-y-1.5">
              {selectedNode.node_type === 'domain' && (
                <Button
                  size="xs"
                  variant="primary"
                  className="w-full"
                  onClick={() => {
                    setSelectedDomain(selectedNode.domain || selectedNode.label);
                    setLevel('sender');
                  }}
                  icon={<Users className="w-3.5 h-3.5" />}
                >
                  Inspect Senders in this Domain
                </Button>
              )}

              <Button
                size="xs"
                variant="outline"
                className="w-full"
                onClick={() => {
                  if (onNavigateToMessages) {
                    onNavigateToMessages(
                      selectedNode.node_type === 'sender'
                        ? selectedNode.address
                        : undefined
                    );
                  }
                }}
                icon={<ExternalLink className="w-3.5 h-3.5" />}
              >
                View Messages in Explorer
              </Button>

              <Button
                size="xs"
                variant="danger"
                className="w-full"
                onClick={() => {
                  if (onNavigateToCleanup) {
                    const conditionField =
                      selectedNode.node_type === 'domain' ? 'sender_domain' : 'sender_address';
                    const conditionVal =
                      selectedNode.node_type === 'domain'
                        ? selectedNode.domain || selectedNode.label
                        : selectedNode.address || selectedNode.label;
                    onNavigateToCleanup({
                      all: [{ field: conditionField, op: 'eq', value: conditionVal }],
                      exclude_protected: true,
                    });
                  }
                }}
                icon={<Trash2 className="w-3.5 h-3.5" />}
              >
                Clean Messages from this Node
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
