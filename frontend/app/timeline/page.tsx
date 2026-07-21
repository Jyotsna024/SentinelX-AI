"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getTimeline, type TimelineItem } from "@/lib/api-client";
import {
  LoadingState, ErrorState, EmptyState, Badge, RiskBadge, Skeleton
} from "@/components/ui/States";
import {
  Activity, Search, AlertTriangle, Shield,
  ChevronDown, ChevronRight, Clock, Filter, RefreshCw,
} from "lucide-react";
import clsx from "clsx";

const POLL_INTERVAL = 5000;

const STAGES = ["all", "predict", "investigate", "contain", "contain_approve"] as const;
type StageFilter = typeof STAGES[number];

const STAGE_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  predict:         { label: "Anomaly Detect",  color: "var(--danger)",  icon: Activity },
  investigate:     { label: "MITRE Analysis",  color: "var(--purple)",  icon: Search },
  contain:         { label: "Containment",     color: "var(--warning)", icon: AlertTriangle },
  contain_approve: { label: "Approved",        color: "var(--success)", icon: Shield },
};

function stageMeta(stage: string) {
  return STAGE_META[stage] ?? { label: stage, color: "var(--accent)", icon: Activity };
}

function formatTs(ts: string) {
  return new Date(ts).toLocaleString([], {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// ── Detail panel for a single timeline node ───────────────────────────────────
function NodeDetail({ item }: { item: TimelineItem }) {
  const p = item.payload;
  const resp = (p.response as Record<string, unknown> | undefined) ?? p;

  if (item.stage === "predict") {
    const score = resp.anomaly_score as number ?? p.anomaly_score;
    const codes = (resp.reason_codes ?? p.reason_codes) as string[] | undefined;
    const isAnom = (resp.is_anomalous ?? p.is_anomalous) as boolean | undefined;
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold" style={{ color: isAnom ? "var(--danger)" : "var(--success)" }}>
            {typeof score === "number" ? score.toFixed(4) : "—"}
          </span>
          <Badge variant={isAnom ? "danger" : "success"}>
            {isAnom ? "ANOMALOUS" : "NORMAL"}
          </Badge>
        </div>
        {codes && codes.length > 0 && (
          <div>
            <p className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>
              Reason Codes
            </p>
            <ul className="space-y-1">
              {codes.map((c, i) => (
                <li key={i} className="text-xs px-2 py-1.5 rounded font-mono"
                  style={{ background: "var(--card-hover)", color: "var(--text-muted)" }}>
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  if (item.stage === "investigate") {
    const techs = (resp.mitre_techniques ?? p.mitre_techniques) as Array<{ id: string; name: string; confidence: number }> | undefined;
    const explanation = (resp.explanation ?? p.explanation) as string | undefined;
    const nextStage = (resp.predicted_next_stage ?? p.predicted_next_stage) as string | undefined;
    const confidence = (resp.attack_confidence ?? p.attack_confidence) as number | undefined;
    return (
      <div className="space-y-3">
        {confidence !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>Attack Confidence:</span>
            <span className="font-bold" style={{ color: "var(--warning)" }}>{(confidence * 100).toFixed(1)}%</span>
          </div>
        )}
        {techs && (
          <div>
            <p className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>MITRE Techniques</p>
            <div className="space-y-1.5">
              {techs.map((t) => (
                <div key={t.id} className="flex items-center gap-2 px-2 py-1.5 rounded"
                  style={{ background: "var(--purple-muted)" }}>
                  <Badge variant="purple">{t.id}</Badge>
                  <span className="text-xs flex-1" style={{ color: "var(--text)" }}>{t.name}</span>
                  <span className="text-xs font-mono" style={{ color: "var(--text-faint)" }}>
                    {(t.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        {nextStage && (
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>Predicted next:</span>
            <Badge variant="warning">{nextStage}</Badge>
          </div>
        )}
        {explanation && (
          <div className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            {explanation}
          </div>
        )}
      </div>
    );
  }

  if (item.stage === "contain" || item.stage === "contain_approve") {
    const riskScore = (resp.risk_score ?? p.risk_score) as number | undefined;
    const riskTier  = (resp.risk_tier  ?? p.risk_tier)  as string | undefined;
    const actions   = (resp.recommended_actions ?? p.recommended_actions) as string[] | undefined;
    const state     = (resp.approval_state ?? p.approval_state) as string | undefined;
    const approver  = p.approver as string | undefined;
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          {typeof riskScore === "number" && (
            <span className="text-2xl font-bold" style={{ color: "var(--warning)" }}>{riskScore}</span>
          )}
          {riskTier && <RiskBadge tier={riskTier} />}
          {state && (
            <Badge variant={state === "executed" ? "success" : state === "rejected" ? "danger" : state === "pending" ? "warning" : "accent"}>
              {state.toUpperCase()}
            </Badge>
          )}
        </div>
        {actions && actions.length > 0 && (
          <div>
            <p className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>
              Recommended Actions
            </p>
            <div className="flex flex-wrap gap-1.5">
              {actions.map((a) => (
                <span key={a} className="text-xs px-2 py-1 rounded font-mono"
                  style={{ background: "var(--warning-muted)", color: "var(--warning)" }}>
                  {a}
                </span>
              ))}
            </div>
          </div>
        )}
        {approver && (
          <div className="text-xs" style={{ color: "var(--text-faint)" }}>
            Approver: <span style={{ color: "var(--text-muted)" }}>{approver}</span>
          </div>
        )}
        {state !== "pending" && (
          <div className="pt-2">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/incident-report/${item.record_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-all hover:brightness-110"
              style={{
                background: "var(--accent-muted)",
                border: "1px solid var(--accent)",
                color: "var(--accent)",
              }}
            >
              Download PDF Report
            </a>
          </div>
        )}
      </div>
    );
  }

  return (
    <pre className="text-xs font-mono overflow-auto max-h-48"
      style={{ color: "var(--text-muted)" }}>
      {JSON.stringify(item.payload, null, 2)}
    </pre>
  );
}

// ── Timeline Node ─────────────────────────────────────────────────────────────
function TimelineNode({
  item,
  isLast,
  isHighlighted,
}: {
  item: TimelineItem;
  isLast: boolean;
  isHighlighted: boolean;
}) {
  const [open, setOpen] = useState(isHighlighted);
  const meta = stageMeta(item.stage);
  const Icon = meta.icon;

  return (
    <div className="flex gap-4 animate-fade-in">
      {/* Spine */}
      <div className="flex flex-col items-center">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 z-10"
          style={{
            background: `${meta.color}22`,
            border: `2px solid ${meta.color}`,
            boxShadow: isHighlighted ? `0 0 14px ${meta.color}` : undefined,
          }}
        >
          <Icon size={14} color={meta.color} />
        </div>
        {!isLast && (
          <div
            className="w-0.5 flex-1 mt-1"
            style={{ background: "var(--border)", minHeight: 24 }}
          />
        )}
      </div>

      {/* Card */}
      <div
        className="flex-1 mb-4 card rounded-xl overflow-hidden"
        style={isHighlighted ? { borderColor: meta.color } : undefined}
      >
        <button
          className="w-full flex items-center gap-3 px-4 py-3 text-left"
          onClick={() => setOpen((v) => !v)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold" style={{ color: meta.color }}>
                {meta.label}
              </span>
              <span className="text-xs" style={{ color: "var(--text-faint)" }}>
                {item.record_id}
              </span>
            </div>
            <div className="flex items-center gap-1 mt-0.5" style={{ color: "var(--text-faint)" }}>
              <Clock size={10} />
              <span className="text-xs">{formatTs(item.timestamp)}</span>
            </div>
          </div>
          {open ? <ChevronDown size={14} style={{ color: "var(--text-faint)" }} /> :
                  <ChevronRight size={14} style={{ color: "var(--text-faint)" }} />}
        </button>

        {open && (
          <div
            className="px-4 pb-4 border-t"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <div className="pt-3">
              <NodeDetail item={item} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Group incidents by record_id ──────────────────────────────────────────────
function groupByRecord(items: TimelineItem[]) {
  const map = new Map<string, TimelineItem[]>();
  for (const item of items) {
    const g = map.get(item.record_id) ?? [];
    g.push(item);
    map.set(item.record_id, g);
  }
  // Sort each group by timestamp ascending
  for (const [, v] of map) v.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  return map;
}

// ── Inner Page (needs Suspense for useSearchParams) ─────────────────────────
function TimelineInner() {
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");

  const [items, setItems] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StageFilter>("all");
  const [selectedRecord, setSelectedRecord] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getTimeline("24h");
      const sorted = [...data.items].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setItems(sorted);
      setError(null);
      // Auto-select record from URL highlight
      if (highlightId) {
        const found = sorted.find((i) => i.id === highlightId);
        if (found) setSelectedRecord(found.record_id);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [highlightId]);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, POLL_INTERVAL);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  const filtered = filter === "all" ? items : items.filter((i) => i.stage === filter);
  const groups = groupByRecord(filtered);
  const recordIds = Array.from(groups.keys());
  const activeRecord = selectedRecord ?? recordIds[0] ?? null;
  const activeGroup = activeRecord ? (groups.get(activeRecord) ?? []) : [];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
        style={{ borderColor: "var(--border)" }}>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text)" }}>Attack Timeline</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
            Incident progression by record
          </p>
        </div>
        <button onClick={fetch} className="p-2 rounded-lg"
          style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
          <RefreshCw size={14} style={{ color: "var(--text-muted)" }} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 px-6 py-3 border-b shrink-0 overflow-x-auto"
        style={{ borderColor: "var(--border-subtle)" }}>
        <Filter size={12} style={{ color: "var(--text-faint)" }} />
        {STAGES.map((s) => (
          <button key={s} onClick={() => setFilter(s)}
            className="px-3 py-1 rounded-full text-xs font-medium capitalize whitespace-nowrap transition-all"
            style={{
              background: filter === s ? "var(--accent)" : "var(--card)",
              color: filter === s ? "#fff" : "var(--text-muted)",
              border: `1px solid ${filter === s ? "var(--accent)" : "var(--border)"}`,
            }}>
            {s === "all" ? "All" : s === "contain_approve" ? "Approved" : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-[260px_1fr]">
        {/* Left: Record list */}
        <div className="border-r overflow-y-auto py-3 px-3"
          style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold uppercase tracking-widest px-2 mb-2"
            style={{ color: "var(--text-faint)" }}>
            Incidents ({recordIds.length})
          </p>
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-lg mb-2" />)
          ) : error ? (
            <ErrorState message={error} onRetry={fetch} />
          ) : recordIds.length === 0 ? (
            <EmptyState title="No incidents" message="No events in the last 24h." />
          ) : (
            recordIds.map((rid) => {
              const stages = groups.get(rid) ?? [];
              const latest = stages[stages.length - 1];
              const meta = stageMeta(latest.stage);
              return (
                <button key={rid} onClick={() => setSelectedRecord(rid)}
                  className={clsx("w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-all")}
                  style={{
                    background: activeRecord === rid ? "var(--card-hover)" : "transparent",
                    borderLeft: activeRecord === rid ? `2px solid ${meta.color}` : "2px solid transparent",
                  }}>
                  <div className="text-xs font-mono truncate" style={{ color: "var(--text)" }}>{rid}</div>
                  <div className="text-xs mt-0.5" style={{ color: meta.color }}>{meta.label}</div>
                </button>
              );
            })
          )}
        </div>

        {/* Right: Timeline nodes */}
        <div className="overflow-y-auto p-6">
          {loading ? (
            <LoadingState message="Loading timeline..." />
          ) : error ? (
            <ErrorState message={error} onRetry={fetch} />
          ) : activeGroup.length === 0 ? (
            <EmptyState title="Select an incident" message="Choose an incident from the left panel." />
          ) : (
            activeGroup.map((item, idx) => (
              <TimelineNode
                key={item.id}
                item={item}
                isLast={idx === activeGroup.length - 1}
                isHighlighted={item.id === highlightId}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ── Export wrapped in Suspense ────────────────────────────────────────────────
export default function TimelinePage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full">
        <div className="text-sm" style={{ color: "var(--text-muted)" }}>Loading timeline...</div>
      </div>
    }>
      <TimelineInner />
    </Suspense>
  );
}
