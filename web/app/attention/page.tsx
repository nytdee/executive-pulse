"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { LensGroup, SignalList, useAttentionGroups } from "@/components/attention-lens";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";

/**
 * Attention — only the items the engine considers worth executive time.
 *
 * The viewer lens (persona or focus profile) groups the queue into
 * "For you" and "Also on your radar" without changing a single score.
 */
export default function AttentionPage() {
  const { referenceMs } = useDashboard();
  const { queue, groups, mode } = useAttentionGroups(20);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Signal"
        title="Attention"
        subtitle="Only items the decision engine considers worth executive time. Every entry states why it surfaced."
      />

      <DataState>
        <Section
          title="Attention queue"
          caption={
            mode === "organization"
              ? `${queue.length} items at Critical or High severity.`
              : `${queue.length} items at Critical or High severity, grouped for you.`
          }
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
      </DataState>
    </AppShell>
  );
}
