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
              // Frosted HUD label styling
              'text-background-color': '#0c0814',
              'text-background-opacity': 0.88,
              'text-background-padding': '3px',
              'text-background-shape': 'roundrectangle',
              'text-border-color': '#3b2066',
              'text-border-width': 1,
              'text-border-opacity': 0.85,
              'transition-property': 'background-color, border-color, width, height, opacity, underlay-opacity',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'node[node_type = "hub"]',
            style: {
              shape: 'hexagon',
              'background-color': '#9333ea',
              'border-color': '#e9d5ff',
              'border-width': 3,
              'font-weight': 'bold',
              'underlay-color': '#a855f7',
              'underlay-padding': '10px',
              'underlay-opacity': 0.35,
              'text-border-color': '#9333ea',
              'text-border-width': 1.5,
            },
          },
          {
            selector: 'node[node_type = "domain"]',
            style: {
              shape: 'round-rectangle',
              'border-color': 'data(color)',
              'border-width': 2.5,
              'underlay-color': 'data(color)',
              'underlay-padding': '4px',
              'underlay-opacity': 0.15,
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
              'border-color': '#f472b6',
              'border-width': 4,
              'underlay-color': '#c084fc',
              'underlay-padding': '8px',
              'underlay-opacity': 0.55,
            },
          },
          {
            selector: 'edge',
            style: {
              width: (ele: any) => {
                const w = ele.data('weight') || 1;
                return `${Math.min(4.5, Math.max(1.2, Math.log2(w + 1)))}px`;
              },
              'line-color': '#6b21a8',
              'curve-style': 'bezier',
              opacity: 0.45,
              'transition-property': 'line-color, width, opacity',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'edge:selected',
            style: {
              'line-color': '#e879f9',
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
              'border-color': '#f472b6',
              'underlay-color': '#a855f7',
              'underlay-padding': '6px',
              'underlay-opacity': 0.35,
            },
          },
          {
            selector: 'node.node-hovered',
            style: {
              'border-width': 3.5,
              'border-color': '#ffffff',
              'underlay-color': '#c084fc',
              'underlay-padding': '10px',
              'underlay-opacity': 0.6,
            },
          },
          {
            selector: 'edge.spotlight',
            style: {
              'line-color': '#e879f9',
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
    <div className="flex-1 flex flex-col h-full bg-[#0c0814] overflow-hidden relative select-none">
      {/* Top Filter and Level Switcher Bar */}
      <div className="p-3 bg-[#120b22]/95 border-b border-purple-900/40 backdrop-blur-md flex flex-wrap items-center justify-between gap-3 z-10 shadow-lg">
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Level Switcher */}
          <div className="flex items-center bg-[#1a0f30] p-0.5 rounded-lg border border-purple-800/40 text-xs shadow-inner">
            <button
              onClick={() => {
                setSelectedDomain('');
                setLevel('domain');
              }}
              className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                level === 'domain'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-950 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Domain Clusters
            </button>
            <button
              onClick={() => setLevel('sender')}
              className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                level === 'sender'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-950 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sender Network
            </button>
          </div>

          {selectedDomain && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-purple-900/30 border border-purple-500/40 text-purple-300 text-xs font-mono">
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
            <Search className="w-3.5 h-3.5 text-purple-400 absolute left-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Find node or domain..."
              className="bg-[#1a0f30] border border-purple-800/40 rounded-lg pl-8 pr-7 py-1 text-xs text-slate-200 placeholder-purple-400/60 focus:outline-none focus:border-purple-500 transition-colors w-44 font-mono"
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
          <div className="flex items-center bg-[#1a0f30] p-0.5 rounded-lg border border-purple-800/40 text-xs shadow-inner">
            <button
              onClick={() => handleApplyLayout('galaxy')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all ${
                layoutMode === 'galaxy'
                  ? 'bg-purple-600 text-white shadow-sm font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Force-directed spring physics layout"
            >
              <Sparkles className="w-3.5 h-3.5 text-fuchsia-300" />
              <span>Galaxy</span>
            </button>
            <button
              onClick={() => handleApplyLayout('hierarchy')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all ${
                layoutMode === 'hierarchy'
                  ? 'bg-purple-600 text-white shadow-sm font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Hierarchical tree branches radiating from root hub"
            >
              <GitFork className="w-3.5 h-3.5 text-cyan-300" />
              <span>Tree</span>
            </button>
            <button
              onClick={() => handleApplyLayout('radial')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all ${
                layoutMode === 'radial'
                  ? 'bg-purple-600 text-white shadow-sm font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Multi-tier concentric planetary orbits"
            >
              <CircleDot className="w-3.5 h-3.5 text-amber-300" />
              <span>Radial</span>
            </button>
            <button
              onClick={() => handleApplyLayout('matrix')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all ${
                layoutMode === 'matrix'
                  ? 'bg-purple-600 text-white shadow-sm font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Ordered technical matrix grid"
            >
              <LayoutGrid className="w-3.5 h-3.5 text-emerald-300" />
              <span>Matrix</span>
            </button>
          </div>

          {/* Sizing Metric Toggle */}
          <div className="flex items-center bg-[#1a0f30] p-0.5 rounded-lg border border-purple-800/40 text-xs">
            <button
              onClick={() => setSizeMetric('count')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md transition-all ${
                sizeMetric === 'count'
                  ? 'bg-purple-800/80 text-white font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Size nodes by email volume"
            >
              <Hash className="w-3 h-3 text-purple-300" />
              <span>Count</span>
            </button>
            <button
              onClick={() => setSizeMetric('size')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md transition-all ${
                sizeMetric === 'size'
                  ? 'bg-purple-800/80 text-white font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Size nodes by total disk storage"
            >
              <HardDrive className="w-3 h-3 text-cyan-300" />
              <span>Storage</span>
            </button>
          </div>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-[#1a0f30] border border-purple-800/40 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
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
            className="border-purple-800/50 hover:bg-purple-900/30 text-purple-200"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Re-simulate
          </Button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 relative w-full h-full">
        {loading && (
          <div className="absolute inset-0 bg-[#0c0814]/75 backdrop-blur-sm flex flex-col items-center justify-center z-20 text-xs font-mono text-purple-200 gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
            <span>Simulating network physics and orbital clusters...</span>
          </div>
        )}

        {/* Cosmic Starfield Grid Canvas */}
        <div
          ref={containerRef}
          className="w-full h-full bg-[#0c0814] bg-[radial-gradient(#3b185f_1px,transparent_1px)] [background-size:28px_28px]"
        />

        {/* Top-Left Telemetry Badges */}
        <div className="absolute top-3 left-4 flex items-center gap-2 pointer-events-none z-10">
          <span className="px-2.5 py-0.5 rounded-full bg-[#170e2c]/90 border border-purple-800/50 text-[10px] font-mono text-purple-300 backdrop-blur-md shadow-md">
            {nodeCount} Nodes
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-[#170e2c]/90 border border-purple-800/50 text-[10px] font-mono text-purple-300 backdrop-blur-md shadow-md">
            {edgeCount} Relations
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-[#170e2c]/90 border border-purple-800/50 text-[10px] font-mono text-fuchsia-300 backdrop-blur-md shadow-md uppercase">
            Layout: {layoutMode}
          </span>
        </div>

        {/* Floating Zoom & Fit Controls */}
        <div className="absolute bottom-5 left-5 flex flex-col gap-1.5 bg-[#170e2c]/90 border border-purple-800/50 rounded-lg p-1.5 shadow-2xl z-20 backdrop-blur-md">
          <button
            onClick={handleZoomIn}
            className="p-1.5 hover:bg-purple-900/40 text-purple-200 rounded transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 hover:bg-purple-900/40 text-purple-200 rounded transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFit}
            className="p-1.5 hover:bg-purple-900/40 text-purple-200 rounded transition-colors"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Node Detail Side Panel */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-84 bg-[#140c26]/95 border border-purple-700/50 shadow-2xl rounded-xl p-4 space-y-3 z-20 backdrop-blur-lg animate-fadeIn text-xs text-slate-200">
            <div className="flex items-start justify-between border-b border-purple-800/40 pb-2.5">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-purple-400 font-semibold">
                  {selectedNode.node_type} Entity
                </span>
                <h4 className="text-sm font-semibold text-white truncate max-w-[210px]">
                  {selectedNode.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
              <div className="p-2.5 bg-[#1e113a] rounded-lg border border-purple-800/40 shadow-inner">
                <div className="text-purple-300 text-[10px]">Email Volume</div>
                <div className="text-sm font-bold text-white mt-0.5">
                  {selectedNode.message_count?.toLocaleString() || 0}
                </div>
              </div>
              <div className="p-2.5 bg-[#1e113a] rounded-lg border border-purple-800/40 shadow-inner">
                <div className="text-purple-300 text-[10px]">Storage Footprint</div>
                <div className="text-sm font-bold text-white mt-0.5">
                  {selectedNode.total_bytes
                    ? `${(selectedNode.total_bytes / (1024 * 1024)).toFixed(2)} MB`
                    : 'N/A'}
                </div>
              </div>
            </div>

            {selectedNode.unread_count !== undefined && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-purple-300">Unread Messages:</span>
                <span className="text-amber-400 font-bold">{selectedNode.unread_count}</span>
              </div>
            )}

            {selectedNode.sender_count !== undefined && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-purple-300">Active Senders:</span>
                <span className="text-cyan-400 font-bold">{selectedNode.sender_count}</span>
              </div>
            )}

            {selectedNode.category && (
              <div className="flex items-center justify-between text-slate-300 font-mono text-[11px] px-1">
                <span className="text-purple-300">Category:</span>
                <Badge label={selectedNode.category} color={selectedNode.color} />
              </div>
            )}

            {/* Quick Drilldown Buttons */}
            <div className="pt-2 border-t border-purple-800/40 space-y-2">
              {selectedNode.node_type === 'domain' && (
                <Button
                  size="xs"
                  variant="primary"
                  className="w-full bg-purple-600 hover:bg-purple-500 shadow-md shadow-purple-950 font-semibold"
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
                className="w-full border-purple-800/50 hover:bg-purple-900/30 text-purple-200"
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
