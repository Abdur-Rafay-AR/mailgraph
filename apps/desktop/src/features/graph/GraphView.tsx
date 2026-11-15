import React, { useEffect, useRef, useState, useMemo } from 'react';
import cytoscape, { Core, EventObject, LayoutOptions } from 'cytoscape';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  ExternalLink,
  Trash2,
  Users,
  Sparkles,
  GitFork,
  CircleDot,
  LayoutGrid,
  Search,
  HardDrive,
  Hash,
  X
} from 'lucide-react';
import { api } from '../../api/client';
import { GraphNodeData, QueryAST } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

interface GraphViewProps {
  onNavigateToMessages?: (senderAddress?: string) => void;
  onNavigateToCleanup?: (query: QueryAST) => void;
}

type LayoutMode = 'galaxy' | 'hierarchy' | 'radial' | 'matrix';

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
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('galaxy');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [nodeCount, setNodeCount] = useState<number>(0);
  const [edgeCount, setEdgeCount] = useState<number>(0);

  // Selected node inspection panel
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);

  const getLayoutConfig = (mode: LayoutMode): LayoutOptions => {
    switch (mode) {
      case 'galaxy':
        return {
          name: 'cose',
          animate: true,
          animationDuration: 700,
          randomize: false,
          componentSpacing: 110,
          nodeRepulsion: () => 550000,
          nodeOverlap: 28,
          idealEdgeLength: () => 95,
          edgeElasticity: () => 100,
          nestingFactor: 5,
          gravity: 55,
          numIter: 1000,
          initialTemp: 250,
          coolingFactor: 0.95,
          minTemp: 1.0,
          padding: 45,
        } as any;
      case 'hierarchy':
        return {
          name: 'breadthfirst',
          directed: true,
          padding: 40,
          spacingFactor: 1.35,
          animate: true,
          animationDuration: 500,
          roots: '[node_type = "hub"]',
        } as any;
      case 'radial':
        return {
          name: 'concentric',
          concentric: (node: any) => {
            if (node.data('node_type') === 'hub') return 100;
            const val = sizeMetric === 'count'
              ? node.data('message_count') || 1
              : node.data('total_bytes') || 1;
            return Math.round(Math.log2(val + 1) * 10);
          },
          levelWidth: () => 15,
          padding: 40,
          animate: true,
          animationDuration: 500,
        } as any;
      case 'matrix':
        return {
          name: 'grid',
          padding: 45,
          avoidOverlap: true,
          animate: true,
          animationDuration: 500,
          sort: (a: any, b: any) => {
            const countA = a.data('message_count') || 0;
            const countB = b.data('message_count') || 0;
            return countB - countA;
          },
        } as any;
    }
  };

  const fetchAndRenderGraph = async () => {
    setLoading(true);
    try {
      const data = await api.getGraph({
        level,
        selected_domain: selectedDomain || undefined,
        category: categoryFilter || undefined,
      });

      if (!containerRef.current) return;

      const nodes = data.elements.nodes || [];
      const edges = data.elements.edges || [];
      setNodeCount(nodes.length);
      setEdgeCount(edges.length);

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
              color: '#e2e8f0',
              'font-size': '11px',
              'font-family': 'JetBrains Mono, ui-monospace, monospace',
              'text-valign': 'bottom',
              'text-margin-y': 7,
              'background-color': 'data(color)',
              'border-width': 2,
              'border-color': '#581c87',
              // Dynamic sizing based on message count vs storage volume
              width: (ele: any) => {
                if (ele.data('node_type') === 'hub') return '62px';
                if (sizeMetric === 'size') {
                  const bytes = ele.data('total_bytes') || 1024;
                  return `${Math.min(78, Math.max(24, Math.log2((bytes / 1024) + 1) * 4.8))}px`;
                }
                const count = ele.data('message_count') || 1;
                return `${Math.min(74, Math.max(22, Math.log2(count + 1) * 8.2))}px`;
              },
              height: (ele: any) => {
                if (ele.data('node_type') === 'hub') return '62px';
                if (sizeMetric === 'size') {
                  const bytes = ele.data('total_bytes') || 1024;
                  return `${Math.min(78, Math.max(24, Math.log2((bytes / 1024) + 1) * 4.8))}px`;
                }
                const count = ele.data('message_count') || 1;
                return `${Math.min(74, Math.max(22, Math.log2(count + 1) * 8.2))}px`;
              },
              // Technical HUD label styling
              'text-background-color': '#0A0A0A',
              'text-background-opacity': 0.92,
              'text-background-padding': '3px',
              'text-background-shape': 'rectangle',
              'text-border-color': '#282828',
              'text-border-width': 1,
              'text-border-opacity': 0.9,
              'transition-property': 'background-color, border-color, width, height, opacity, underlay-opacity',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'node[node_type = "hub"]',
            style: {
              shape: 'ellipse',
              'background-color': '#FF3B30',
              'border-color': '#ffffff',
              'border-width': 3,
              'font-weight': 'bold',
              'underlay-color': '#FF3B30',
              'underlay-padding': '8px',
              'underlay-opacity': 0.35,
              'text-border-color': '#FF3B30',
              'text-border-width': 1,
            },
          },
          {
            selector: 'node[node_type = "domain"]',
            style: {
              shape: 'ellipse',
              'border-color': 'data(color)',
              'border-width': 2.5,
              'underlay-color': 'data(color)',
              'underlay-padding': '5px',
              'underlay-opacity': 0.25,
            },
          },
          {
            selector: 'node[node_type = "sender"]',
            style: {
              shape: 'ellipse',
              'border-color': 'data(color)',
              'border-width': 2,
            },
          },
          {
            selector: 'node:selected',
            style: {
              'border-color': '#FF3B30',
              'border-width': 3.5,
              'underlay-color': '#FF3B30',
              'underlay-padding': '8px',
              'underlay-opacity': 0.45,
            },
          },
          {
            selector: 'edge',
            style: {
              width: (ele: any) => {
                const w = ele.data('weight') || 1;
                return `${Math.min(4.5, Math.max(1.2, Math.log2(w + 1)))}px`;
              },
              'line-color': '#2A2A2E',
              'curve-style': 'bezier',
              opacity: 0.6,
              'transition-property': 'line-color, width, opacity',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'edge:selected',
            style: {
              'line-color': '#FF3B30',
              width: 3.5,
              opacity: 1,
            },
          },
          // Spotlight hover radar classes
          {
            selector: '.dimmed',
            style: {
              opacity: 0.12,
            },
          },
          {
            selector: '.spotlight',
            style: {
              opacity: 1,
              'z-index': 999,
            },
          },
          {
            selector: 'node.spotlight',
            style: {
              'border-width': 3,
              'border-color': '#FF3B30',
              'underlay-color': '#FF3B30',
              'underlay-padding': '6px',
              'underlay-opacity': 0.35,
            },
          },
          {
            selector: 'node.node-hovered',
            style: {
              'border-width': 3,
              'border-color': '#ffffff',
              'underlay-color': '#FF3B30',
              'underlay-padding': '8px',
              'underlay-opacity': 0.5,
            },
          },
          {
            selector: 'edge.spotlight',
            style: {
              'line-color': '#FF3B30',
              opacity: 0.95,
              width: (ele: any) => {
                const w = ele.data('weight') || 1;
                return `${Math.min(6, Math.max(2.2, Math.log2(w + 1) * 1.5))}px`;
              },
            },
          },
          {
            selector: '.search-matched',
            style: {
              'border-color': '#38bdf8',
              'border-width': 4,
              'underlay-color': '#38bdf8',
              'underlay-padding': '12px',
              'underlay-opacity': 0.55,
              opacity: 1,
            },
          },
        ],
        layout: getLayoutConfig(layoutMode),
      });

      // Interactive Spotlight Radar on Node Hover
      cy.on('mouseover', 'node', (evt: EventObject) => {
        const targetNode = evt.target;
        const neighborhood = targetNode.closedNeighborhood();
        cy.elements().removeClass('spotlight node-hovered').addClass('dimmed');
        neighborhood.removeClass('dimmed').addClass('spotlight');
        targetNode.addClass('node-hovered');
      });

      cy.on('mouseout', 'node', () => {
        cy.elements().removeClass('spotlight dimmed node-hovered');
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
      console.error('Failed to render graph topology:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAndRenderGraph();
  }, [level, selectedDomain, categoryFilter, sizeMetric]);

  // Handle Layout Mode switch without re-fetching data
  const handleApplyLayout = (mode: LayoutMode) => {
    setLayoutMode(mode);
    if (!cyRef.current) return;
    const config = getLayoutConfig(mode);
    cyRef.current.layout(config).run();
  };

  // Search filter across rendered nodes
  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    if (!cyRef.current) return;

    cyRef.current.elements().removeClass('search-matched');

    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return;

    const matched = cyRef.current.nodes().filter((ele) => {
      const label = (ele.data('label') || '').toLowerCase();
      const domain = (ele.data('domain') || '').toLowerCase();
      const address = (ele.data('address') || '').toLowerCase();
      return label.includes(trimmed) || domain.includes(trimmed) || address.includes(trimmed);
    });

    if (matched.length > 0) {
      matched.addClass('search-matched');
      cyRef.current.animate({
        center: { eles: matched.first() },
        zoom: Math.min(1.6, cyRef.current.zoom() * 1.3),
        duration: 450,
      });
    }
  };

  // Layout resets and zoom
  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit(undefined, 50);
  const handleResetLayout = () => {
    if (!cyRef.current) return;
    cyRef.current.layout(getLayoutConfig(layoutMode)).run();
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden relative select-none">
      {/* Top Filter and Level Switcher Bar */}
      <div className="p-3 bg-bg-surface border-b border-border-subtle flex flex-wrap items-center justify-between gap-3 z-10 shadow-sm">
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Level Switcher */}
          <div className="flex items-center bg-bg-deep p-0.5 rounded-none border border-border-muted text-xs">
            <button
              onClick={() => {
                setSelectedDomain('');
                setLevel('domain');
              }}
              className={`px-3 py-1.5 rounded-none font-mono text-xs transition-all ${
                level === 'domain'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Domain Clusters
            </button>
            <button
              onClick={() => setLevel('sender')}
              className={`px-3 py-1.5 rounded-none font-mono text-xs transition-all ${
                level === 'sender'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sender Network
            </button>
          </div>

          {selectedDomain && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-none bg-bg-elevated border border-brand text-brand-light text-xs font-mono">
              Filtered Domain: {selectedDomain}
              <button
                onClick={() => {
                  setSelectedDomain('');
                  setLevel('domain');
                }}
                className="hover:text-white font-bold ml-1 transition-colors"
                title="Clear domain filter"
              >
                ×
              </button>
            </span>
          )}

          {/* Quick Node Search */}
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Find node or domain..."
              className="bg-bg-deep border border-border-muted rounded-none pl-8 pr-7 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand transition-colors w-44 font-mono"
            />
            {searchQuery && (
              <button
                onClick={() => handleSearchChange('')}
                className="absolute right-2 text-slate-400 hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Topology & Physics Layout Modes */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Topology Switcher */}
          <div className="flex items-center bg-bg-deep p-0.5 rounded-none border border-border-muted text-xs">
            <button
              onClick={() => handleApplyLayout('galaxy')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-none font-mono text-xs transition-all ${
                layoutMode === 'galaxy'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Force-directed spring physics layout"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Galaxy</span>
            </button>
            <button
              onClick={() => handleApplyLayout('hierarchy')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-none font-mono text-xs transition-all ${
                layoutMode === 'hierarchy'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Hierarchical tree branches radiating from root hub"
            >
              <GitFork className="w-3.5 h-3.5" />
              <span>Tree</span>
            </button>
            <button
              onClick={() => handleApplyLayout('radial')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-none font-mono text-xs transition-all ${
                layoutMode === 'radial'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Multi-tier concentric planetary orbits"
            >
              <CircleDot className="w-3.5 h-3.5" />
              <span>Radial</span>
            </button>
            <button
              onClick={() => handleApplyLayout('matrix')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-none font-mono text-xs transition-all ${
                layoutMode === 'matrix'
                  ? 'bg-brand text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Ordered technical matrix grid"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Matrix</span>
            </button>
          </div>

          {/* Sizing Metric Toggle */}
          <div className="flex items-center bg-bg-deep p-0.5 rounded-none border border-border-muted text-xs">
            <button
              onClick={() => setSizeMetric('count')}
              className={`flex items-center gap-1 px-2 py-1 rounded-none font-mono text-xs transition-all ${
                sizeMetric === 'count'
                  ? 'bg-bg-elevated text-white font-bold border border-border-muted'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Size nodes by email volume"
            >
              <Hash className="w-3 h-3 text-slate-400" />
              <span>Count</span>
            </button>
            <button
              onClick={() => setSizeMetric('size')}
              className={`flex items-center gap-1 px-2 py-1 rounded-none font-mono text-xs transition-all ${
                sizeMetric === 'size'
                  ? 'bg-bg-elevated text-white font-bold border border-border-muted'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Size nodes by total disk storage"
            >
              <HardDrive className="w-3 h-3 text-slate-400" />
              <span>Storage</span>
            </button>
          </div>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-bg-deep border border-border-muted rounded-none px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand font-mono"
          >
            <option value="">All Categories</option>
            <option value="important">Important</option>
            <option value="personal">Personal</option>
            <option value="work">Work</option>
            <option value="newsletter">Newsletters</option>
            <option value="receipt_invoice">Receipts</option>
            <option value="security">Security</option>
            <option value="promotional">Promotional</option>
            <option value="transactional">Transactional</option>
          </select>

          <Button
            size="xs"
            variant="outline"
            onClick={handleResetLayout}
            title="Re-run physics simulation"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Re-simulate
          </Button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 relative w-full h-full">
        {loading && (
          <div className="absolute inset-0 bg-bg-deep/80 backdrop-blur-sm flex flex-col items-center justify-center z-20 text-xs font-mono text-slate-300 gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-brand" />
            <span>Simulating network physics and orbital clusters...</span>
          </div>
        )}

        {/* Technical Grid Canvas */}
        <div
          ref={containerRef}
          className="w-full h-full bg-[#0A0A0A] bg-[radial-gradient(#262626_1px,transparent_1px)] [background-size:24px_24px]"
        />

        {/* Top-Left Telemetry Badges */}
        <div className="absolute top-3 left-4 flex items-center gap-2 pointer-events-none z-10">
          <span className="px-2.5 py-0.5 rounded-none bg-bg-surface/90 border border-border-muted text-[10px] font-mono text-slate-300 shadow-sm">
            {nodeCount} Nodes
          </span>
          <span className="px-2.5 py-0.5 rounded-none bg-bg-surface/90 border border-border-muted text-[10px] font-mono text-slate-300 shadow-sm">
            {edgeCount} Relations
          </span>
          <span className="px-2.5 py-0.5 rounded-none bg-bg-surface/90 border border-border-muted text-[10px] font-mono text-brand font-bold shadow-sm uppercase">
            Layout: {layoutMode}
          </span>
        </div>

        {/* Floating Zoom & Fit Controls */}
        <div className="absolute bottom-5 left-5 flex flex-col gap-1.5 bg-bg-surface border border-border-muted rounded-none p-1.5 shadow-xl z-20">
          <button
            onClick={handleZoomIn}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 hover:text-white rounded-none transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 hover:text-white rounded-none transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFit}
            className="p-1.5 hover:bg-bg-elevated text-slate-300 hover:text-white rounded-none transition-colors"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Node Detail Side Panel */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-84 bg-bg-surface border border-border-muted shadow-2xl rounded-none p-4 space-y-3 z-20 animate-fadeIn text-xs text-slate-200 font-mono">
            <div className="flex items-start justify-between border-b border-border-subtle pb-2.5">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-brand font-bold">
                  {selectedNode.node_type} Entity
                </span>
                <h4 className="text-sm font-bold text-white truncate max-w-[210px] font-sans">
                  {selectedNode.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1 rounded-none transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
              <div className="p-2.5 bg-bg-deep rounded-none border border-border-subtle">
                <div className="text-slate-400 text-[10px] uppercase">Email Volume</div>
                <div className="text-sm font-bold text-white mt-0.5">
                  {selectedNode.message_count?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 bg-bg-deep rounded-none border border-border-subtle">
                <div className="text-slate-400 text-[10px] uppercase">Storage</div>
                <div className="text-sm font-bold text-white mt-0.5">
                  {selectedNode.total_bytes
                    ? `${(selectedNode.total_bytes / (1024 * 1024)).toFixed(2)} MB`
                    : 'N/A'}
                </div>
              </div>
            </div>

            {selectedNode.unread_count !== undefined && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-slate-400">Unread Messages:</span>
                <span className="text-brand font-bold">{selectedNode.unread_count}</span>
              </div>
            )}

            {selectedNode.sender_count !== undefined && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-slate-400">Active Senders:</span>
                <span className="text-white font-bold">{selectedNode.sender_count}</span>
              </div>
            )}

            {selectedNode.category && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-slate-400">Category:</span>
                <Badge label={selectedNode.category} color={selectedNode.color} />
              </div>
            )}

            {/* Quick Drilldown Buttons */}
            <div className="pt-2 border-t border-border-subtle space-y-2">
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
