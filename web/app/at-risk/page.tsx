"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { SignalRowWithDetail } from "@/components/signal-row";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getAtRisk } from "@/lib/rule-engine";

/**
 * At Risk — work approaching a deadline, plus high-impact open work.
 */
export default function AtRiskPage() {
  const { tasks, referenceMs } = useDashboard();
  const items = getAtRisk(tasks);

  const byDepartment = new Map<string, typeof items>();
  for (const task of items) {
    const list = byDepartment.get(task.Department) ?? [];
    list.push(task);
    byDepartment.set(task.Department, list);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Exceptions"
        title="At Risk"
        subtitle="Where execution could miss, why, and what it affects."
      />

      <DataState>
        <Section
          title="Execution risk"
          caption={`${items.length} issues could materially affect execution.`}
        >
          {items.length === 0 ? (
            <EmptyState>No material execution risks right now.</EmptyState>
          ) : (
            Array.from(byDepartment.entries())
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([department, departmentItems]) => (
                <div key={department}>
                  <div className="ep-group-label">{department}</div>
                  {departmentItems.map((task) => (
                    <SignalRowWithDetail
                      key={task.Task_ID}
                      task={task}
                      referenceMs={referenceMs}
                    />
                  ))}
                </div>
              ))
          )}
        </Section>
      </DataState>
    </AppShell>
  );
}
