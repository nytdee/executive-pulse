"use client";

/**
 * Executive Pulse — application shell.
 *
 * A quiet left rail with navigation, viewer controls and the data
 * source. The main column carries exactly one thing: the answer to
 * "what do I need to know".
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ControlsPanel } from "@/components/controls-panel";
import { DataSourcePanel } from "@/components/data-source-panel";
import { useDashboard } from "@/components/dashboard-provider";

export const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/my-decisions", label: "My Input Required" },
  { href: "/attention", label: "Attention" },
  { href: "/decisions", label: "All Decisions" },
  { href: "/at-risk", label: "At Risk" },
  { href: "/blocked", label: "Blocked" },
  { href: "/changes", label: "Changes" },
  { href: "/org-pulse", label: "Org Pulse" },
  { href: "/stale", label: "Stale Work" },
  { href: "/meeting-brief", label: "Meeting Brief" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { counts, loading, error } = useDashboard();

  const countFor = (href: string): number | undefined => {
    if (href === "/") return counts.open;
    if (href === "/attention") return counts.attention;
    if (href === "/decisions") return counts.decisions;
    if (href === "/my-decisions") return counts.decisions;
    if (href === "/at-risk") return counts.atRisk;
    if (href === "/blocked") return counts.blocked;
    if (href === "/stale") return counts.stale;
    return undefined;
  };

  return (
    <div className="ep-shell">
      <aside className="ep-sidebar">
        <div className="ep-brand">Executive Pulse</div>
        <div className="ep-brand-subtitle">
          Decision intelligence for leadership
        </div>

        <div className="ep-sidebar-label">Navigate</div>
        <nav className="ep-nav">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const count = countFor(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className="ep-nav-link"
                data-active={active}
              >
                <span>{item.label}</span>
                {count !== undefined && count > 0 ? (
                  <span className="ep-nav-count">{count}</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <ControlsPanel />
        <DataSourcePanel />

        <div
          className="ep-freshness"
          style={{ marginTop: "1.75rem", fontSize: "0.6875rem" }}
        >
          {loading ? "Loading…" : error ? "Data unavailable" : "Live"}
        </div>
      </aside>

      <main className="ep-main">
        <div className="ep-container">{children}</div>
      </main>
    </div>
  );
}
