"use client";

/**
 * Executive Pulse — shared view primitives.
 *
 * The header, the section framing and the empty states used by every
 * page. Kept in one place so the hierarchy is identical throughout.
 */

import Link from "next/link";

import { useDashboard } from "@/components/dashboard-provider";
import { formatReferenceDay } from "@/lib/format";
import type { Counts } from "@/lib/types";

/** The executive header: state, then a calm summary strip. */
export function ExecutiveHeader({
  counts,
  referenceMs,
  total,
}: {
  counts: Counts;
  referenceMs: number;
  total: number;
}) {
  const day = formatReferenceDay(referenceMs);

  return (
    <header>
      <div className="ep-eyebrow">Executive operating layer</div>
      <h1 className="ep-title">Executive Pulse</h1>
      <div className="ep-state-line">
        <strong>{day}</strong> · {counts.attention} things require your
        attention.
      </div>
      <div className="ep-freshness">
        {counts.decisions} decisions waiting · {counts.critical} critical risks
        · {counts.blocked} blocked items
        <br />
        Data refreshed: {total} items
      </div>

      <div className="ep-summary">
        <SummaryItem label="Open" value={counts.open} />
        <SummaryItem label="Attention" value={counts.attention} />
        <SummaryItem label="Critical" value={counts.critical} tone="critical" />
        <SummaryItem label="At Risk" value={counts.atRisk} tone="warning" />
        <SummaryItem label="Decisions" value={counts.decisions} />
        <SummaryItem label="Blocked" value={counts.blocked} />
      </div>
    </header>
  );
}

function SummaryItem({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "critical" | "warning";
}) {
  return (
    <div className="ep-summary-item" data-tone={tone}>
      <span className="ep-summary-label">{label}</span>
      <span className="ep-summary-value">{value}</span>
    </div>
  );
}

/** A section heading with an optional caption and action. */
export function Section({
  title,
  caption,
  children,
  action,
}: {
  title: string;
  caption?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="ep-section">
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "1rem",
        }}
      >
        <div>
          <div className="ep-section-title">{title}</div>
          {caption ? <div className="ep-section-caption">{caption}</div> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A quiet link used as a section action. */
export function SectionLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="ep-button"
      data-variant="quiet"
      style={{ fontSize: "0.75rem" }}
    >
      {children}
    </Link>
  );
}

/** An empty state that explains itself. */
export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="ep-empty">{children}</div>;
}

/** A page header for the focused views. */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <div className="ep-eyebrow">{eyebrow}</div>
      <h1 className="ep-title">{title}</h1>
      <p className="ep-subtitle">{subtitle}</p>
    </div>
  );
}

/** Loading and error states for the whole view. */
export function DataState({ children }: { children: React.ReactNode }) {
  const { loading, error } = useDashboard();

  if (error) {
    return (
      <div
        className="ep-empty"
        style={{ color: "var(--color-critical)", marginTop: "2rem" }}
      >
        {error}
      </div>
    );
  }
  if (loading) {
    return <div className="ep-empty">Loading…</div>;
  }
  return <>{children}</>;
}
