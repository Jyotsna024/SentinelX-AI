"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  Network,
  ShieldAlert,
  Activity,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/timeline", label: "Timeline", icon: GitBranch },
  { href: "/network-graph", label: "Network", icon: Network },
  { href: "/approval-panel", label: "Approvals", icon: ShieldAlert },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="flex flex-col w-60 shrink-0 h-screen border-r"
      style={{
        background: "var(--card)",
        borderColor: "var(--border)",
      }}
    >
      {/* Brand */}
      <div
        className="flex items-center gap-3 px-5 py-5 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: "var(--danger)", boxShadow: "0 0 12px var(--danger)" }}
        >
          <Activity size={16} color="#fff" />
        </div>
        <div>
          <div className="font-semibold text-sm leading-tight" style={{ color: "var(--text)" }}>
            SentinelX AI
          </div>
          <div className="text-xs" style={{ color: "var(--text-faint)" }}>
            SOC Platform
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                active
                  ? "text-white"
                  : "hover:text-white"
              )}
              style={{
                background: active ? "var(--accent-muted)" : "transparent",
                color: active ? "var(--accent)" : "var(--text-muted)",
                borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
              }}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        className="px-5 py-4 border-t text-xs"
        style={{ borderColor: "var(--border)", color: "var(--text-faint)" }}
      >
        <div>Phase 2 Backend</div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <span
            className="w-1.5 h-1.5 rounded-full inline-block"
            style={{ background: "var(--success)" }}
          />
          <span style={{ color: "var(--text-muted)" }}>Connected</span>
        </div>
      </div>
    </aside>
  );
}
