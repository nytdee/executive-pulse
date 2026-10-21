"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { SignalRowWithDetail } from "@/components/signal-row";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getDecisionQueueDetailed } from "@/lib/intelligence";

/**
 * Decisions — the module that makes this a decision layer rather than a
 * dashboard. What is needed, why now, who is waiting, what it costs.
 */
export default function DecisionsPage() {
  const { tasks, referenceMs } = useDashboard();
  const decisions = getDecisionQueueDetailed(tasks, referenceMs);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Input required"
        title="Decisions"
        subtitle="Decisions currently waiting on an executive. Each one states what is needed, when it is needed, and who is waiting."
      />

      <DataState>
        <Section
          title="Decision queue"
          caption={`${decisions.length} decisions waiting for executive input.`}
        >
          {decisions.length === 0 ? (
            <EmptyState>No decisions waiting for executive input.</EmptyState>
          ) : (
            decisions.map((task) => (
              <SignalRowWithDetail
                key={task.Task_ID}
                task={task}
                referenceMs={referenceMs}
              />
            ))
          )}
        </Section>
      </DataState>
    </AppShell>
  );
}
