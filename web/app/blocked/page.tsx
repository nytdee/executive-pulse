"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { SignalRowWithDetail } from "@/components/signal-row";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getBlockedFrictionDetailed } from "@/lib/intelligence";
import { formatMoney } from "@/lib/format";

/**
 * Blocked — where the organization is getting stuck.
 *
 * Grouped by blocker rather than by task, because the executive question
 * is "where are we stuck", not "list every blocked item".
 */
export default function BlockedPage() {
  const { tasks, referenceMs } = useDashboard();
  const detail = getBlockedFrictionDetailed(tasks, referenceMs);

  const groups = new Map<string, typeof tasks>();
  for (const task of tasks.filter((item) => item.blocked)) {
    const key = (task.Blocker ?? "").trim() || "Unspecified blocker";
    const list = groups.get(key) ?? [];
    list.push(task);
    groups.set(key, list);
  }
  const sortedGroups = Array.from(groups.entries()).sort(
    ([, a], [, b]) => b.length - a.length,
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Friction"
        title="Blocked"
        subtitle="Where the organization is stuck, grouped by blocker."
      />

      <DataState>
        <Section
          title="Blocked work"
          caption={`${detail.summary.total_blocked} items blocked across ${detail.summary.departments_affected} departments.`}
        >
          {detail.summary.total_blocked === 0 ? (
            <EmptyState>Nothing is blocked right now.</EmptyState>
          ) : (
            sortedGroups.map(([blocker, blockedItems]) => {
              const departments = Array.from(
                new Set(blockedItems.map((task) => task.Department)),
              );
              const impact = blockedItems.reduce(
                (sum, task) => sum + (task.Impact_Value ?? 0),
                0,
              );

              const bits = [
                `${blockedItems.length} items blocked`,
                departments.slice(0, 3).join(", "),
              ];
              const money = formatMoney(impact);
              if (money) bits.push(`${money} affected`);

              return (
                <div key={blocker}>
                  <div className="ep-group-label">{blocker}</div>
                  <div className="ep-group-summary">{bits.join(" · ")}</div>
                  {blockedItems.map((task) => (
                    <SignalRowWithDetail
                      key={task.Task_ID}
                      task={task}
                      referenceMs={referenceMs}
                    />
                  ))}
                </div>
              );
            })
          )}
        </Section>

        {detail.crossTeam.length > 0 ? (
          <Section
            title="Cross-team friction"
            caption="One team's work is blocking another."
          >
            {detail.crossTeam.map((point) => (
              <div className="sig" key={point.blocker_owner}>
                <span
                  className="sig-bar"
                  data-tone={
                    point.severity === "Critical"
                      ? "critical"
                      : point.severity === "High"
                        ? "warning"
                        : "muted"
                  }
                  aria-hidden="true"
                />
                <div className="sig-main">
                  <div className="sig-title">{point.blocker_owner}</div>
                  <div className="sig-meta">
                    {point.blocker_dept || "Unknown team"}
                  </div>
                  <div className="sig-impact">
                    {point.blocked_count} items blocked
                    {point.max_days_blocked > 0
                      ? ` · oldest ${point.max_days_blocked}d`
                      : ""}
                  </div>
                  <div className="sig-signal">
                    <strong>{point.severity}</strong>
                    {formatMoney(point.total_impact_value)
                      ? ` · ${formatMoney(point.total_impact_value)} at risk`
                      : ""}
                  </div>
                </div>
              </div>
            ))}
          </Section>
        ) : null}
      </DataState>
    </AppShell>
  );
}
