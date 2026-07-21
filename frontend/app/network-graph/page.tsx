"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  MarkerType,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { getTimeline, type TimelineItem } from "@/lib/api-client";
import { ErrorState, Badge, RiskBadge } from "@/components/ui/States";
import { RefreshCw, Info } from "lucide-react";

const POLL_INTERVAL = 5000;

// ── Asset criticality lookup (mirrors backend asset_criticality_lookup.json) ──
const ASSETS: Record<string, { label: string; criticality: number }> = {
  internet:           { label: "Internet",          criticality: 0 },
  firewall:           { label: "Firewall",           criticality: 8 },
  employee_laptop:    { label: "Employee Laptop",    criticality: 3 },
  domain_controller:  { label: "Domain Controller",  criticality: 9 },
  hospital_db:        { label: "Hospital DB",        criticality: 10 },
  backup_server:      { label: "Backup Server",      criticality: 7 },
};

// ── Fixed node positions (deterministic, no random) ───────────────────────────
const FIXED_POSITIONS: Record<string, { x: number; y: number }> = {
  internet:          { x: 300, y: 20  },
  firewall:          { x: 300, y: 130 },
  employee_laptop:   { x: 300, y: 240 },
  domain_controller: { x: 300, y: 350 },
  hospital_db:       { x: 300, y: 460 },
  backup_server:     { x: 300, y: 570 },
};

// ── Fixed edges (network topology) ───────────────────────────────────────────
const TOPOLOGY_EDGES: Array<{ source: string; target: string }> = [
  { source: "internet",          target: "firewall" },
  { source: "firewall",          target: "employee_laptop" },
  { source: "employee_laptop",   target: "domain_controller" },
  { source: "domain_controller", target: "hospital_db" },
  { source: "hospital_db",       target: "backup_server" },
];

// ── Custom Node Component ─────────────────────────────────────────────────────
function AssetNode({ data }: { data: { label: string; criticality: number; isActive: boolean; activeInfo?: ActiveInfo } }) {
  const { label, criticality, isActive, activeInfo } = data;
  const critColor =
    criticality >= 9 ? "var(--danger)" :
    criticality >= 7 ? "var(--warning)" :
    criticality >= 4 ? "var(--accent)" : "var(--success)";

  return (
    <div
      className="relative"
      style={{ width: 200 }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "var(--border)", border: "none" }} />
      <div
        className="rounded-xl px-4 py-3 transition-all duration-300"
        style={{
          background: isActive ? `${activeInfo?.color ?? "var(--danger)"}22` : "var(--card)",
          border: `1.5px solid ${isActive ? (activeInfo?.color ?? "var(--danger)") : "var(--border)"}`,
          boxShadow: isActive ? `0 0 16px ${activeInfo?.color ?? "var(--danger)"}66` : undefined,
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium" style={{ color: "var(--text)" }}>{label}</span>
          <span
            className="text-xs font-mono px-1.5 py-0.5 rounded"
            style={{ background: `${critColor}22`, color: critColor, fontSize: 10 }}
          >
            C:{criticality}
          </span>
        </div>
        {isActive && activeInfo && (
          <div className="mt-1.5 text-xs font-medium" style={{ color: activeInfo.color }}>
            ⚠ {activeInfo.tier.toUpperCase()} — Score {activeInfo.score}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: "var(--border)", border: "none" }} />
    </div>
  );
}

const nodeTypes = { asset: AssetNode };

interface ActiveInfo {
  score: number;
  tier: string;
  color: string;
}

// ── Build graph nodes + edges from active incident data ───────────────────────
function buildGraph(activeAssets: Map<string, ActiveInfo>) {
  const nodes: Node[] = Object.entries(ASSETS).map(([id, asset]) => ({
    id,
    type: "asset",
    position: FIXED_POSITIONS[id],
    data: {
      label: asset.label,
      criticality: asset.criticality,
      isActive: activeAssets.has(id),
      activeInfo: activeAssets.get(id),
    },
    draggable: false,
  }));

  const edges: Edge[] = TOPOLOGY_EDGES.map(({ source, target }) => {
    const targetActive = activeAssets.has(target);
    const tierColor = activeAssets.get(target)?.color;
    return {
      id: `${source}-${target}`,
      source,
      target,
      type: "smoothstep",
      animated: targetActive,
      style: {
        stroke: targetActive ? tierColor : "var(--border)",
        strokeWidth: targetActive ? 2.5 : 1.5,
        strokeDasharray: targetActive ? "6 3" : undefined,
        filter: targetActive ? `drop-shadow(0 0 4px ${tierColor})` : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: targetActive ? tierColor! : "var(--border)",
      },
    };
  });

  return { nodes, edges };
}

function tierColor(tier: string) {
  return tier === "critical" ? "var(--danger)" : tier === "elevated" ? "var(--warning)" : "var(--success)";
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function NetworkGraphPage() {
  const [activeAssets, setActiveAssets] = useState<Map<string, ActiveInfo>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [incidents, setIncidents] = useState<TimelineItem[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getTimeline("24h");
      const containItems = data.items.filter((i) => i.stage === "contain" || i.source === "audit_log");

      // Extract active (pending or recently executed) asset incidents
      const map = new Map<string, ActiveInfo>();
      for (const item of containItems) {
        const p = item.payload;
        const resp = (p.response as Record<string, unknown> | undefined) ?? p;
        const assetId = (p.request as Record<string, unknown> | undefined)?.asset_id as string | undefined;
        const riskTier  = (resp.risk_tier  ?? p.risk_tier)  as string | undefined;
        const riskScore = (resp.risk_score ?? p.risk_score) as number | undefined;
        const state     = (resp.approval_state ?? p.approval_state) as string | undefined;

        if (assetId && riskTier && riskScore !== undefined && state !== "rejected") {
          if (!map.has(assetId) || (map.get(assetId)!.score < riskScore)) {
            map.set(assetId, {
              score: riskScore,
              tier: riskTier,
              color: tierColor(riskTier),
            });
          }
        }
      }

      setActiveAssets(map);
      setIncidents(containItems.slice(0, 6));
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, POLL_INTERVAL);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  const { nodes, edges } = buildGraph(activeAssets);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
        style={{ borderColor: "var(--border)" }}>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text)" }}>Network Attack Map</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
            Asset topology with live threat overlay
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetch} className="p-2 rounded-lg"
            style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
            <RefreshCw size={14} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-[1fr_300px]">
        {/* Graph */}
        <div className="relative" style={{ background: "var(--bg)" }}>
          {error ? (
            <div className="p-6">
              <ErrorState message={error} onRetry={fetch} />
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="var(--border-subtle)" gap={24} size={1} />
              <Controls
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <MiniMap
                nodeColor={(n) => n.data?.isActive ? (n.data?.activeInfo?.color ?? "#6366f1") : "#1e2d45"}
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
              />
            </ReactFlow>
          )}
        </div>

        {/* Right: Legend + Active incidents */}
        <div className="border-l overflow-y-auto p-4 space-y-4"
          style={{ borderColor: "var(--border)" }}>
          {/* Legend */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3"
              style={{ color: "var(--text-faint)" }}>Legend</p>
            <div className="space-y-2">
              {[
                { color: "var(--danger)",  label: "Critical (score >90)" },
                { color: "var(--warning)", label: "Elevated (40–90)" },
                { color: "var(--success)", label: "Monitor (<40)" },
                { color: "var(--border)",  label: "No active threat" },
              ].map((l) => (
                <div key={l.label} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: l.color }} />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{l.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="h-px" style={{ background: "var(--border-subtle)" }} />

          {/* Criticality table */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3"
              style={{ color: "var(--text-faint)" }}>Asset Criticality</p>
            <div className="space-y-1.5">
              {Object.entries(ASSETS).filter(([id]) => id !== "internet").map(([id, asset]) => (
                <div key={id} className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>{asset.label}</span>
                  <span className="text-xs font-mono" style={{ color: "var(--text-faint)" }}>{asset.criticality}/10</span>
                </div>
              ))}
            </div>
          </div>

          <div className="h-px" style={{ background: "var(--border-subtle)" }} />

          {/* Active threat list */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3 flex items-center gap-2"
              style={{ color: "var(--text-faint)" }}>
              Active Threats
              {activeAssets.size > 0 && <Badge variant="danger">{activeAssets.size}</Badge>}
            </p>
            {activeAssets.size === 0 ? (
              <div className="text-xs" style={{ color: "var(--text-faint)" }}>
                No active threats detected.
              </div>
            ) : (
              Array.from(activeAssets.entries()).map(([id, info]) => (
                <div key={id} className="card rounded-lg px-3 py-2 mb-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium" style={{ color: "var(--text)" }}>
                      {ASSETS[id]?.label ?? id}
                    </span>
                    <RiskBadge tier={info.tier} />
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
                    Risk score: <span style={{ color: info.color }}>{info.score}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Info note */}
          <div className="rounded-lg px-3 py-2.5 flex gap-2"
            style={{ background: "var(--card-hover)", border: "1px solid var(--border-subtle)" }}>
            <Info size={12} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
            <span className="text-xs leading-relaxed" style={{ color: "var(--text-faint)" }}>
              Nodes pulse when an active contain event targets that asset. Edges animate to show lateral movement direction.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
