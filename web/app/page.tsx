"use client";

import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { LensGroup, SignalList, useAttentionGroups } from "@/components/attention-lens";
import {
  DataState,
  EmptyState,
  ExecutiveHeader,
  Section,
  SectionLink,
} from "@/components/views";
import { getOrgPulseEnhanced } from "@/lib/intelligence";
import { getCounts } from "@/lib/rule-engine";

/**
 * Overview — the 60-second view.
 *
 * Order matters: state, what needs attention, where the organization is
 * stuck. Everything else is one click away.
 */
export default function OverviewPage() {
  const { tasks, counts, referenceMs } = useDashboard();
  const { queue, groups, mode } = useAttentionGroups(5);
  const org = getOrgPulseEnhanced(tasks).slice(0, 5);

  return (
    <AppShell>
      <ExecutiveHeader
        counts={counts}
        referenceMs={referenceMs}
        total={tasks.length}
      />

      <DataState>
        <Section
          title="What needs your attention"
          caption={
            mode === "organization"
              ? "The highest-priority exceptions surfaced by the decision engine."
              : "The highest-priority exceptions, grouped for you. Scores are unchanged."
          }
          action={<SectionLink href="/attention">View all</SectionLink>}
        >
          {queue.length === 0 ? (
            <EmptyState>Nothing requires executive attention right now.</EmptyState>
          ) : groups.length > 0 ? (
            groups.map((group) => (
              <LensGroup
                key={group.key}
                label={group.label}
                caption={group.caption}
                tasks={group.tasks}
                matches={"matches" in group ? group.matches : undefined}
                referenceMs={referenceMs}
              />
            ))
          ) : (
            <SignalList tasks={queue} referenceMs={referenceMs} />
          )}
        </Section>

        <Section
          title="Organization"
          caption="Where the organization is experiencing friction."
          action={<SectionLink href="/org-pulse">View all</SectionLink>}
        >
          {org.length === 0 ? (
            <EmptyState>No department data.</EmptyState>
          ) : (
            org.map((row) => {
              const bits: string[] = [];
              if (row.High_Impact > 0) bits.push(`${row.High_Impact} critical`);
              if (row.Blocked > 0) bits.push(`${row.Blocked} blocked`);
              if (row.Decisions > 0) bits.push(`${row.Decisions} decision`);
              if (row.At_Risk > 0) bits.push(`${row.At_Risk} at risk`);
              if (bits.length === 0) bits.push(`${row.Open} open`);

              return (
                <div className="sig" key={row.Department}>
                  <span
                    className="sig-bar"
                    data-tone={
                      row.Risk_Score >= 60
                        ? "critical"
                        : row.Risk_Score >= 30
                          ? "warning"
                          : "muted"
                    }
                    aria-hidden="true"
                  />
                  <div className="sig-main">
                    <div className="sig-title">{row.Department}</div>
                    <div className="sig-signal">{bits.join(" · ")}</div>
                  </div>
                  <div className="sig-side">
                    <span className="ep-nav-count">risk {row.Risk_Score}</span>
                  </div>
                </div>
              );
            })
          )}
        </Section>

        <Section
          title="Decisions waiting"
          caption="What is blocked on you specifically."
          action={<SectionLink href="/decisions">View all</SectionLink>}
        >
          {counts.decisions === 0 ? (
            <EmptyState>No decisions waiting for executive input.</EmptyState>
          ) : (
            <div className="ep-group-summary">
              {counts.decisions} decisions currently require executive input.
            </div>
          )}
        </Section>

        <Section
          title="What changed"
          caption="Meaningful changes since your last review."
          action={<SectionLink href="/changes">View all</SectionLink>}
        >
          <EmptyState>
            Change detection compares against the previous refresh.{" "}
            <Link href="/changes">Open Changes</Link> to see the current delta.
          </EmptyState>
        </Section>
      </DataState>
    </AppShell>
  );
}
