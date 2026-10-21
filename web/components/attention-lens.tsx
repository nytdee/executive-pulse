"use client";

/**
 * Executive Pulse — the attention queue with the viewer lens applied.
 *
 * This is where the persona lens and the freeform focus profile become
 * visible. Both only *group* the engine ranking — the score, the order
 * and the reason codes are exactly what the rules produced.
 *
 *   For you            — matches your lens, or your focus terms
 *   Also on your radar — everything else, still engine-ranked
 */

import { SignalRowWithDetail } from "@/components/signal-row";
import { useDashboard } from "@/components/dashboard-provider";
import {
  groupByPersona,
  groupByProfile,
  personaDepartments,
} from "@/lib/persona";
import { getExecutiveAttentionQueue } from "@/lib/rule-engine";
import type { ScoredTask } from "@/lib/types";

export function LensGroup({
  label,
  caption,
  tasks,
  matches,
  referenceMs,
}: {
  label: string;
  caption?: string;
  tasks: ScoredTask[];
  matches?: Map<string, string[]>;
  referenceMs: number;
}) {
  if (tasks.length === 0) return null;

  return (
    <div>
      {label ? <div className="ep-group-label">{label}</div> : null}
      {caption ? <div className="ep-group-summary">{caption}</div> : null}
      {tasks.map((task) => (
        <SignalRowWithDetail
          key={task.Task_ID}
          task={task}
          referenceMs={referenceMs}
          matchTerms={matches?.get(task.Task_ID)}
        />
      ))}
    </div>
  );
}

/** A flat, ungrouped list of items. */
export function SignalList({
  tasks,
  referenceMs,
}: {
  tasks: ScoredTask[];
  referenceMs: number;
}) {
  return (
    <div>
      {tasks.map((task) => (
        <SignalRowWithDetail
          key={task.Task_ID}
          task={task}
          referenceMs={referenceMs}
        />
      ))}
    </div>
  );
}

/**
 * Resolve the attention queue into lens-aware groups.
 * Returns null when no lens is active, so callers can render a flat
 * queue instead.
 */
export function useAttentionGroups(maxItems = 20) {
  const { tasks, referenceMs, persona, focusKeywords } = useDashboard();

  const queue = getExecutiveAttentionQueue(tasks, maxItems, "High");

  // A focus profile overrides the persona lens while it is active.
  if (focusKeywords.length > 0) {
    const grouped = groupByProfile(queue, focusKeywords, maxItems);
    if (grouped) {
      return {
        queue,
        mode: "focus" as const,
        groups: [
          {
            key: "for-you",
            label: "For you",
            caption: `Matching your focus: ${focusKeywords.slice(0, 4).join(", ")}`,
            tasks: grouped.mine,
            matches: grouped.matches,
          },
          {
            key: "radar",
            label: "Also on your radar",
            caption: "Everything else, still ranked by the engine.",
            tasks: grouped.rest,
          },
        ],
      };
    }
  }

  const departments =
    persona && persona !== "CEO" && persona !== "Chief of Staff"
      ? personaDepartments(persona)
      : null;

  if (departments) {
    const grouped = groupByPersona(queue, persona, maxItems);
    return {
      queue,
      mode: "persona" as const,
      groups: [
        {
          key: "for-you",
          label: "For you",
          caption: `Your departments: ${departments.join(", ")}`,
          tasks: grouped.mine,
        },
        {
          key: "radar",
          label: "Also on your radar",
          caption: "The rest of the organization, still ranked by the engine.",
          tasks: grouped.rest,
        },
      ],
    };
  }

  return { queue, mode: "organization" as const, groups: [] };
}
