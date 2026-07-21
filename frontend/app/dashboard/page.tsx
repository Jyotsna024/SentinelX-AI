"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCri, getTimeline, type CriResponse, type TimelineItem } from "@/lib/api-client";
import { LoadingState, ErrorState, EmptyState, Badge, RiskBadge, Skeleton } from "@/components/ui/States";
import {
  TrendingUp, TrendingDown, Minus, Activity, AlertTriangle,
  Clock, RefreshCw, Zap, Shield, Search,
} from "lucide-react";

const POLL_INTERVAL = 5000;

// ── CRI Gauge Component ──────────────────────────────────────────────────────
function CriGauge({ cri }: { cri: CriResponse }) {
  const { score, status, trend, factors } = cri;
  const radius = 80;
  const stroke = 10;
  const normalizedRadius = radius - stroke / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const colorMap: Record<string, string> = {
    healthy: "var(--success)",
    elevated: "var(--warning)",
    critical: "var(--danger)",
  };
  const color = colorMap[status] ?? "var(--accent)";

  const TrendIcon =
    trend === "improving" ? TrendingUp :
    trend === "declining" ? TrendingDown : Minus;
  const trendColor =
    trend === "improving" ? "var(--success)" :
    trend === "declining" ? "var(--danger)" : "var(--text-muted)";

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Radial Gauge */}
      <div className="relative">
        <svg height={radius * 2} width={radius * 2} className="rotate-[-90deg]">
          {/* Track */}
          <circle
            stroke="var(--border)"
            fill="transparent"
            strokeWidth={stroke}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
          />
          {/* Score Arc */}
          <circle
            stroke={color}
            fill="transparent"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
            style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)", filter: `drop-shadow(0 0 6px ${color})` }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold tabular-nums" style={{ color }}>
            {score}
          </span>
          <span className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            CRI Score
          </span>
        </div>
      </div>

      {/* Status + Trend */}
      <div className="flex items-center gap-3">
        <RiskBadge tier={status} />
        <div className="flex items-center gap-1 text-sm font-medium" style={{ color: trendColor }}>
          <TrendIcon size={14} />
          <span className="capitalize">{trend}</span>
        </div>
      </div>

      {/* Factor Cards */}
      <div className="grid grid-cols-3 gap-3 w-full">
        {[
          { label: "Active Anomalies", value: factors.active_anomalies, color: "var(--danger)" },
          { label: "Open Incidents", value: factors.unresolved_incidents, color: "var(--warning)" },
          { label: "Avg Risk Score", value: factors.avg_risk_score.toFixed(1), color: "var(--text)" },
        ].map((f) => (
          <div
            key={f.label}
            className="card rounded-xl p-3 text-center"
          >
            <div className="text-xl font-bold tabular-nums" style={{ color: f.color }}>
              {f.value}
            </div>
            <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
              {f.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stage icon + color map ────────────────────────────────────────────────────
const STAGE_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  predict:        { label: "Anomaly", color: "var(--danger)",  icon: Activity },
  investigate:    { label: "Analysis", color: "var(--purple)", icon: Search },
  contain:        { label: "Contain",  color: "var(--warning)", icon: AlertTriangle },
  contain_approve:{ label: "Approved", color: "var(--success)", icon: Shield },
};

function stageMeta(stage: string) {
  return STAGE_META[stage] ?? { label: stage, color: "var(--accent)", icon: Zap };
}

function formatTime(ts: string) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function AlertCard({ item, onClick }: { item: TimelineItem; onClick: () => void }) {
  const meta = stageMeta(item.stage);
  const Icon = meta.icon;

  // Extract short summary from payload
  let summary = `Record: ${item.record_id}`;
  const p = item.payload;
  const resp = (p.response as Record<string, unknown> | undefined) ?? p;
  if (item.stage === "predict" && typeof resp.anomaly_score === "number") {
    summary = `Score: ${(resp.anomaly_score as number).toFixed(3)} | ${resp.is_anomalous ? "⚠ Anomalous" : "✓ Normal"}`;
  } else if (item.stage === "investigate" && Array.isArray(resp.mitre_techniques)) {
    const techs = (resp.mitre_techniques as { id: string }[]).map((t) => t.id).join(", ");
    summary = `Techniques: ${techs || "—"}`;
  } else if (item.stage === "contain" && typeof resp.risk_score === "number") {
    summary = `Risk: ${resp.risk_score} (${resp.risk_tier}) | ${(resp.recommended_actions as string[])?.length ?? 0} actions`;
  } else if (item.stage === "contain_approve") {
    summary = `State: ${p.approval_state ?? "—"} | Approver: ${p.approver ?? "—"}`;
  }

  return (
    <button
      onClick={onClick}
      className="w-full text-left card card-hover rounded-xl p-3 flex items-start gap-3 animate-fade-in"
    >
      <div
        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: `${meta.color}22` }}
      >
        <Icon size={13} color={meta.color} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold" style={{ color: meta.color }}>
            {meta.label}
          </span>
          <span className="text-xs truncate" style={{ color: "var(--text-faint)" }}>
            {item.record_id}
          </span>
        </div>
        <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{summary}</p>
      </div>
      <div className="flex items-center gap-1 shrink-0" style={{ color: "var(--text-faint)" }}>
        <Clock size={10} />
        <span className="text-xs">{formatTime(item.timestamp)}</span>
      </div>
    </button>
  );
}

// ── Main Dashboard Page ───────────────────────────────────────────────────────
export default function DashboardPage() {
  const [cri, setCri] = useState<CriResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [criError, setCriError] = useState<string | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [criLoading, setCriLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCri = useCallback(async () => {
    try {
      const data = await getCri();
      setCri(data);
      setCriError(null);
    } catch (e) {
      setCriError((e as Error).message);
    } finally {
      setCriLoading(false);
    }
  }, []);

  const fetchTimeline = useCallback(async () => {
    try {
      const data = await getTimeline("24h");
      const sorted = [...data.items].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setTimeline(sorted);
      setTimelineError(null);
    } catch (e) {
      setTimelineError((e as Error).message);
    } finally {
      setTimelineLoading(false);
      setLastUpdated(new Date());
    }
  }, []);

  const fetchAll = useCallback(() => {
    fetchCri();
    fetchTimeline();
  }, [fetchCri, fetchTimeline]);

  useEffect(() => {
    fetchAll();
    intervalRef.current = setInterval(fetchAll, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchAll]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-4 border-b shrink-0"
        style={{ borderColor: "var(--border)" }}
      >
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text)" }}>
            Security Dashboard
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
            Cyber Resilience Index &amp; Live Alerts
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchAll}
            className="p-2 rounded-lg transition-colors"
            style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            title="Refresh now"
          >
            <RefreshCw size={14} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-[340px_1fr] xl:grid-cols-[380px_1fr]">
        {/* Left: CRI Panel */}
        <div
          className="border-r p-6 overflow-auto"
          style={{ borderColor: "var(--border)" }}
        >
          <h2 className="text-xs font-semibold uppercase tracking-widest mb-5"
            style={{ color: "var(--text-faint)" }}>
            Resilience Index
          </h2>
          {criLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-40 w-40 rounded-full mx-auto" />
              <Skeleton className="h-8 rounded-xl" />
              <div className="grid grid-cols-3 gap-3">
                <Skeleton className="h-16 rounded-xl" />
                <Skeleton className="h-16 rounded-xl" />
                <Skeleton className="h-16 rounded-xl" />
              </div>
            </div>
          ) : criError ? (
            <ErrorState message={criError} onRetry={fetchCri} />
          ) : cri ? (
            <CriGauge cri={cri} />
          ) : null}

          {/* Poll indicator */}
          <div className="mt-6 flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "var(--success)", boxShadow: "0 0 6px var(--success)", animation: "pulse 2s infinite" }}
            />
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>
              Polling every {POLL_INTERVAL / 1000}s
            </span>
          </div>
        </div>

        {/* Right: Live Alerts Feed */}
        <div className="flex flex-col overflow-hidden">
          <div
            className="flex items-center justify-between px-6 py-3 border-b"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <h2 className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: "var(--text-faint)" }}>
              Live Alerts Feed
            </h2>
            <Badge variant="accent">{timeline.length}</Badge>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {timelineLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-xl" />
              ))
            ) : timelineError ? (
              <ErrorState message={timelineError} onRetry={fetchTimeline} />
            ) : timeline.length === 0 ? (
              <EmptyState
                title="No alerts yet"
                message="Events will appear here as the backend processes network flows."
                icon={<Activity size={36} />}
              />
            ) : (
              timeline.map((item) => (
                <AlertCard
                  key={item.id}
                  item={item}
                  onClick={() => {
                    window.location.href = `/timeline?highlight=${item.id}`;
                  }}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
