"use client";

import { Loader2 } from "lucide-react";

// ── Skeleton ──────────────────────────────────────────────────────
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded ${className}`}
      style={{ background: "var(--card-hover)" }}
    />
  );
}

// ── Loading Overlay ───────────────────────────────────────────────
export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3">
      <Loader2
        size={28}
        className="animate-spin"
        style={{ color: "var(--accent)" }}
      />
      <span className="text-sm" style={{ color: "var(--text-muted)" }}>
        {message}
      </span>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────
export function EmptyState({
  title = "No data",
  message = "No records found for the selected window.",
  icon,
}: {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-center px-6">
      {icon && (
        <div style={{ color: "var(--text-faint)" }} className="mb-1">
          {icon}
        </div>
      )}
      <p className="font-medium" style={{ color: "var(--text-muted)" }}>
        {title}
      </p>
      <p className="text-sm" style={{ color: "var(--text-faint)" }}>
        {message}
      </p>
    </div>
  );
}

// ── Error State ───────────────────────────────────────────────────
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-center px-6">
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: "var(--danger-muted)" }}
      >
        <span style={{ color: "var(--danger)", fontSize: 20 }}>!</span>
      </div>
      <p className="font-medium" style={{ color: "var(--danger)" }}>
        Connection Error
      </p>
      <p className="text-sm max-w-xs" style={{ color: "var(--text-muted)" }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
          style={{
            background: "var(--card-hover)",
            border: "1px solid var(--border)",
            color: "var(--text)",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────
export function Badge({
  children,
  variant = "accent",
  className = "",
}: {
  children: React.ReactNode;
  variant?: "danger" | "warning" | "success" | "accent" | "purple" | "muted";
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium badge-${variant} ${className}`}
    >
      {children}
    </span>
  );
}

// ── Status Badge for risk_tier / cri.status ───────────────────────
export function RiskBadge({ tier }: { tier: string }) {
  const map: Record<string, "danger" | "warning" | "success"> = {
    critical: "danger",
    elevated: "warning",
    monitor: "success",
    healthy: "success",
  };
  return <Badge variant={map[tier] ?? "accent"}>{tier.toUpperCase()}</Badge>;
}

// ── Divider ───────────────────────────────────────────────────────
export function Divider({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-px w-full ${className}`}
      style={{ background: "var(--border-subtle)" }}
    />
  );
}
