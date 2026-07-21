"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getTimeline, approveContain, type TimelineItem, type ApproveResponse } from "@/lib/api-client";
import { LoadingState, ErrorState, EmptyState, Badge, RiskBadge } from "@/components/ui/States";
import {
  Shield, AlertTriangle, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, RefreshCw, User,
} from "lucide-react";

const POLL_INTERVAL = 5000;

// ── Confirmation Dialog ───────────────────────────────────────────────────────
function ConfirmDialog({
  item,
  onConfirm,
  onCancel,
}: {
  item: PendingItem;
  onConfirm: (approver: string, approved: boolean) => void;
  onCancel: () => void;
}) {
  const [approver, setApprover] = useState("");
  const [approving, setApproving] = useState(true);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)" }}>
      <div className="card rounded-2xl w-full max-w-md p-6 animate-fade-in"
        style={{ border: "1px solid var(--border)" }}>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: approving ? "var(--success-muted)" : "var(--danger-muted)" }}>
            {approving
              ? <CheckCircle2 size={20} color="var(--success)" />
              : <XCircle size={20} color="var(--danger)" />}
          </div>
          <div>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>
              {approving ? "Approve Incident?" : "Reject Incident?"}
            </h2>
            <p className="text-xs" style={{ color: "var(--text-faint)" }}>{item.record_id}</p>
          </div>
        </div>

        {/* Risk info */}
        <div className="rounded-xl px-4 py-3 mb-4 space-y-2"
          style={{ background: "var(--card-hover)", border: "1px solid var(--border-subtle)" }}>
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>Risk Score</span>
            <span className="font-bold text-lg" style={{ color: "var(--warning)" }}>{item.risk_score}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-faint)" }}>Risk Tier</span>
            <RiskBadge tier={item.risk_tier} />
          </div>
          {item.recommended_actions.length > 0 && (
            <div>
              <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>Actions</p>
              <div className="flex flex-wrap gap-1.5">
                {item.recommended_actions.map((a) => (
                  <div key={a} className="flex items-center gap-1.5">
                    <CheckCircle2 size={10} color="var(--success)" />
                    <span className="text-xs font-mono" style={{ color: "var(--text)" }}>{a}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Toggle approve/reject */}
        <div className="flex gap-2 mb-4">
          {[true, false].map((v) => (
            <button key={String(v)} onClick={() => setApproving(v)}
              className="flex-1 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{
                background: approving === v ? (v ? "var(--success-muted)" : "var(--danger-muted)") : "var(--card)",
                color: approving === v ? (v ? "var(--success)" : "var(--danger)") : "var(--text-muted)",
                border: `1px solid ${approving === v ? (v ? "var(--success)" : "var(--danger)") : "var(--border)"}`,
              }}>
              {v ? "Approve" : "Reject"}
            </button>
          ))}
        </div>

        {/* Approver name */}
        <div className="mb-5">
          <label className="text-xs mb-1.5 block" style={{ color: "var(--text-muted)" }}>
            Operator Name
          </label>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg"
            style={{ background: "var(--card-hover)", border: "1px solid var(--border)" }}>
            <User size={13} style={{ color: "var(--text-faint)" }} />
            <input
              type="text"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="e.g. sec_operator_01"
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: "var(--text)" }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button onClick={onCancel}
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: "var(--card-hover)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
            }}>
            Cancel
          </button>
          <button
            onClick={() => approver.trim() && onConfirm(approver.trim(), approving)}
            disabled={!approver.trim()}
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
            style={{
              background: approving ? "var(--success)" : "var(--danger)",
              color: "#fff",
            }}>
            {approving ? "Approve" : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Pending Incident Card ─────────────────────────────────────────────────────
interface PendingItem {
  audit_log_id: string;
  record_id: string;
  risk_score: number;
  risk_tier: string;
  recommended_actions: string[];
  mitre_techniques?: Array<{ id: string; name: string; confidence: number }>;
  approval_state: string;
  result?: ApproveResponse;
}

function PendingCard({
  item,
  onAction,
}: {
  item: PendingItem;
  onAction: (item: PendingItem) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const tierColor =
    item.risk_tier === "critical" ? "var(--danger)" :
    item.risk_tier === "elevated" ? "var(--warning)" : "var(--success)";

  const isResolved = item.result !== undefined;

  return (
    <div className="card rounded-xl overflow-hidden animate-fade-in"
      style={isResolved ? { borderColor: item.result?.status === "executed" ? "var(--success)" : "var(--danger)" } : {}}>
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${tierColor}22` }}>
          <AlertTriangle size={14} color={tierColor} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>
              {item.record_id}
            </span>
            <RiskBadge tier={item.risk_tier} />
            {isResolved ? (
              <Badge variant={item.result?.status === "executed" ? "success" : "danger"}>
                {item.result?.status?.toUpperCase()}
              </Badge>
            ) : (
              <Badge variant="warning">PENDING</Badge>
            )}
          </div>
          <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
            Audit: {item.audit_log_id.slice(0, 12)}…
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xl font-bold tabular-nums" style={{ color: tierColor }}>
            {item.risk_score}
          </span>
          <button onClick={() => setExpanded((v) => !v)}>
            {expanded ? <ChevronUp size={16} style={{ color: "var(--text-faint)" }} /> :
                        <ChevronDown size={16} style={{ color: "var(--text-faint)" }} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 border-t space-y-3"
          style={{ borderColor: "var(--border-subtle)" }}>
          <div className="pt-3">
            {/* Actions list */}
            {item.recommended_actions.length > 0 && (
              <div className="mb-3">
                <p className="text-xs font-semibold uppercase tracking-wide mb-1.5"
                  style={{ color: "var(--text-faint)" }}>Recommended Actions</p>
                <div className="flex flex-wrap gap-1.5">
                  {item.recommended_actions.map((a) => (
                    <span key={a} className="text-xs px-2 py-1 rounded font-mono"
                      style={{ background: "var(--warning-muted)", color: "var(--warning)" }}>
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* MITRE techniques if available */}
            {item.mitre_techniques && item.mitre_techniques.length > 0 && (
              <div className="mb-3">
                <p className="text-xs font-semibold uppercase tracking-wide mb-1.5"
                  style={{ color: "var(--text-faint)" }}>MITRE Techniques</p>
                <div className="space-y-1">
                  {item.mitre_techniques.map((t) => (
                    <div key={t.id} className="flex items-center gap-2">
                      <Badge variant="purple">{t.id}</Badge>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>{t.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Result */}
            {isResolved && item.result && (
              <div className="rounded-lg px-3 py-2"
                style={{
                  background: item.result.status === "executed" ? "var(--success-muted)" : "var(--danger-muted)",
                  border: `1px solid ${item.result.status === "executed" ? "var(--success)" : "var(--danger)"}`,
                }}>
                <p className="text-xs font-semibold" style={{
                  color: item.result.status === "executed" ? "var(--success)" : "var(--danger)"
                }}>
                  {item.result.status === "executed"
                    ? `✓ ${item.result.executed_actions.length} actions executed`
                    : "✗ Incident rejected"}
                </p>
              </div>
            )}
          </div>

          {/* Action button */}
          {!isResolved && (
            <button
              onClick={() => onAction(item)}
              className="w-full py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2"
              style={{
                background: "var(--accent-muted)",
                border: "1px solid var(--accent)",
                color: "var(--accent)",
              }}>
              <Shield size={14} />
              Review &amp; Approve / Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function ApprovalPanelPage() {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogItem, setDialogItem] = useState<PendingItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getTimeline("24h");
      // Only show audit_log entries that are pending approval
      const pendingItems: PendingItem[] = data.items
        .filter((i) => i.source === "audit_log" && i.payload.approval_state === "pending")
        .map((i) => {
          const p = i.payload;
          return {
            audit_log_id: i.id,
            record_id: i.record_id,
            risk_score: (p.risk_score as number) ?? 0,
            risk_tier: (p.risk_tier as string) ?? "monitor",
            recommended_actions: (p.recommended_actions as string[]) ?? [],
            approval_state: (p.approval_state as string) ?? "pending",
          };
        })
        // Sort by risk_score descending (most critical first)
        .sort((a, b) => b.risk_score - a.risk_score);

      setPending((prev) => {
        // Preserve local resolution results from previous state
        return pendingItems.map((item) => {
          const existing = prev.find((p) => p.audit_log_id === item.audit_log_id);
          return existing?.result ? { ...item, result: existing.result } : item;
        });
      });
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, POLL_INTERVAL);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch]);

  const handleConfirm = useCallback(async (approver: string, approved: boolean) => {
    if (!dialogItem) return;
    setActionLoading(true);
    try {
      const result = await approveContain({
        audit_log_id: dialogItem.audit_log_id,
        approved,
        approver,
      });
      setPending((prev) =>
        prev.map((p) =>
          p.audit_log_id === dialogItem.audit_log_id ? { ...p, result } : p
        )
      );
    } catch (e) {
      alert(`Failed: ${(e as Error).message}`);
    } finally {
      setActionLoading(false);
      setDialogItem(null);
    }
  }, [dialogItem]);

  const resolvedCount = pending.filter((p) => p.result).length;
  const unresolvedCount = pending.filter((p) => !p.result).length;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
        style={{ borderColor: "var(--border)" }}>
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: "var(--text)" }}>
            <Shield size={18} style={{ color: "var(--accent)" }} />
            Approval Panel
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
            Incident Commander — Human escalation gate
          </p>
        </div>
        <div className="flex items-center gap-3">
          {unresolvedCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg animate-glow-warning"
              style={{ background: "var(--warning-muted)", border: "1px solid var(--warning)" }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--warning)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--warning)" }}>
                {unresolvedCount} pending
              </span>
            </div>
          )}
          <button onClick={fetch} className="p-2 rounded-lg"
            style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
            <RefreshCw size={14} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {!loading && pending.length > 0 && (
        <div className="flex gap-4 px-6 py-3 border-b shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}>
          {[
            { label: "Total", value: pending.length, color: "var(--text)" },
            { label: "Pending", value: unresolvedCount, color: "var(--warning)" },
            { label: "Resolved", value: resolvedCount, color: "var(--success)" },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-2">
              <span className="text-lg font-bold tabular-nums" style={{ color: s.color }}>{s.value}</span>
              <span className="text-xs" style={{ color: "var(--text-faint)" }}>{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <LoadingState message="Fetching pending approvals..." />
        ) : error ? (
          <ErrorState message={error} onRetry={fetch} />
        ) : pending.length === 0 ? (
          <EmptyState
            title="No pending approvals"
            message="All incidents have been reviewed or no critical/elevated threats are active."
            icon={<CheckCircle2 size={40} />}
          />
        ) : (
          <div className="max-w-2xl mx-auto space-y-3">
            {pending.map((item) => (
              <PendingCard
                key={item.audit_log_id}
                item={item}
                onAction={setDialogItem}
              />
            ))}
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      {dialogItem && !actionLoading && (
        <ConfirmDialog
          item={dialogItem}
          onConfirm={handleConfirm}
          onCancel={() => setDialogItem(null)}
        />
      )}
      {actionLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.6)" }}>
          <div className="card rounded-xl p-6 flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 rounded-full animate-spin"
              style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>Submitting decision...</span>
          </div>
        </div>
      )}
    </div>
  );
}
