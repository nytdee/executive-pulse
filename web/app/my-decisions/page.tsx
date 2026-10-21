"use client";

/**
 * Executive Pulse — "My input required".
 *
 * The view a CXO actually opens: the decisions waiting on *them*,
 * scoped to their department or their focus, with what each one needs,
 * who is waiting, and by when.
 *
 * The scoping never changes a score. It only narrows the queue.
 */

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { SignalRowWithDetail } from "@/components/signal-row";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getDecisionQueueDetailed } from "@/lib/intelligence";
import { personaDepartments, profileRelevance } from "@/lib/persona";
import type { ScoredTask } from "@/lib/types";

/**
 * Decide which decisions are the viewer's.
 *
 * Priority:
 *  1. An explicit focus profile — if the viewer wrote "design", only
 *     decisions matching those terms are theirs.
 *  2. A department persona — CMO sees Marketing and Sales.
 *  3. Otherwise everything (CEO / Chief of Staff see the whole org).
 */
export function scopeDecisionsToViewer(
  decisions: ScoredTask[],
  persona: string,
  focusKeywords: string[],
): { mine: ScoredTask[]; scope: string } {
  if (focusKeywords.length > 0) {
    const mine = decisions.filter(
      (task) => profileRelevance(task as unknown as Record<string, unknown>, focusKeywords).score > 0,
    );
    return {
      mine,
      scope: `matching your focus: ${focusKeywords.slice(0, 4).join(", ")}`,
    };
  }

  const departments = personaDepartments(persona);
  if (departments) {
    return {
      mine: decisions.filter((task) => departments.includes(task.Department)),
      scope: `your departments: ${departments.join(", ")}`,
    };
  }

  return { mine: decisions, scope: "the whole organization" };
}

export default function MyDecisionsPage() {
  const { tasks, referenceMs, persona, focusKeywords } = useDashboard();
  const all = getDecisionQueueDetailed(tasks, referenceMs);
  const { mine, scope } = scopeDecisionsToViewer(all, persona, focusKeywords);

  const urgent = mine.filter((task) =>
    String((task as unknown as { decision_urgency?: string }).decision_urgency ?? "").startsWith("URGENT"),
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Waiting on you"
        title="My Input Required"
        subtitle="Decisions waiting on you specifically, scoped to what you own. Scores and urgency are unchanged."
      />

      <DataState>
        <Section
          title="Decisions for you"
          caption={`${mine.length} of ${all.length} decisions · ${scope}`}
        >
          {mine.length === 0 ? (
            <EmptyState>
              Nothing is waiting on you right now.{" "}
              {all.length > 0
                ? `${all.length} decisions are open across the organization.`
                : "No decisions are open across the organization."}
            </EmptyState>
          ) : (
            mine.map((task) => (
              <SignalRowWithDetail
                key={task.Task_ID}
                task={task}
                referenceMs={referenceMs}
              />
            ))
          )}
        </Section>

        {urgent.length > 0 ? (
          <Section
            title="Most urgent"
            caption="Overdue or due today. These are the ones that cost you if they slip."
          >
            {urgent.map((task) => (
              <SignalRowWithDetail
                key={task.Task_ID}
                task={task}
                referenceMs={referenceMs}
              />
            ))}
          </Section>
        ) : null}
      </DataState>
    </AppShell>
  );
}
