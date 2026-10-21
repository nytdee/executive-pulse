"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { SignalRowWithDetail } from "@/components/signal-row";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getStaleWork } from "@/lib/rule-engine";
import { daysSince, formatMoney } from "@/lib/format";

/**
 * Stale Work — work that has not materially progressed.
 */
export default function StalePage() {
  const { tasks, referenceMs } = useDashboard();
  const items = getStaleWork(tasks);

  const byDepartment = new Map<string, typeof items>();
  for (const task of items) {
    const list = byDepartment.get(task.Department) ?? [];
    list.push(task);
    byDepartment.set(task.Department, list);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Drift"
        title="Stale Work"
        subtitle="Work that has not materially progressed. Items with no update for more than 48 hours."
      />

      <DataState>
        <Section
          title="Stale items"
          caption={`${items.length} items have not materially progressed.`}
        >
          {items.length === 0 ? (
            <EmptyState>Everything is progressing. No stale work.</EmptyState>
          ) : (
            Array.from(byDepartment.entries())
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([department, departmentItems]) => {
                const ages = departmentItems
                  .map((task) => daysSince(task.Last_Updated, referenceMs))
                  .filter((age): age is number => age !== null);
                const oldest = ages.length > 0 ? Math.max(...ages) : 0;
                const impact = departmentItems.reduce(
                  (sum, task) => sum + (task.Impact_Value ?? 0),
                  0,
                );

                const bits = [`${departmentItems.length} stale items`];
                if (oldest > 0) bits.push(`oldest ${oldest}d`);
                const money = formatMoney(impact);
                if (money) bits.push(`${money} impact`);

                return (
                  <div key={department}>
                    <div className="ep-group-label">{department}</div>
                    <div className="ep-group-summary">{bits.join(" · ")}</div>
                    {departmentItems.map((task) => (
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
      </DataState>
    </AppShell>
  );
}
