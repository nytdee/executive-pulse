"use client";

/**
 * Executive Pulse — sidebar navigation.
 *
 * Text-first, quiet, and counts inline so an executive can see where
 * the pressure is without clicking.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface NavItem {
  href: string;
  label: string;
  count?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview" },
  { href: "/attention", label: "Attention" },
  { href: "/decisions", label: "Decisions" },
  { href: "/at-risk", label: "At Risk" },
  { href: "/blocked", label: "Blocked" },
  { href: "/changes", label: "Changes" },
  { href: "/org-pulse", label: "Org Pulse" },
  { href: "/stale", label: "Stale Work" },
  { href: "/meeting-brief", label: "Meeting Brief" },
];

export function Sidebar({
  counts,
  children,
}: {
  counts?: Record<string, number>;
  children?: React.ReactNode;
}) {
  const pathname = usePathname();

  const countFor = (href: string): number | undefined => {
    if (!counts) return undefined;
    if (href === "/") return counts.open;
    if (href === "/attention") return counts.attention;
    if (href === "/decisions") return counts.decisions;
    if (href === "/at-risk") return counts.atRisk;
    if (href === "/blocked") return counts.blocked;
    if (href === "/stale") return counts.stale;
    return undefined;
  };

  return (
    <aside className="ep-sidebar">
      <div className="ep-brand">Executive Pulse</div>
      <div className="ep-brand-subtitle">Decision intelligence for leadership</div>

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

      {children}
    </aside>
  );
}
