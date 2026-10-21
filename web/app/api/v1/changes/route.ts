/**
 * GET /api/v1/changes — what changed since the last review.
 *
 * Change detection needs to remember the previous state of the data.
 * On Vercel the filesystem is ephemeral, so the baseline is kept in a
 * small server-side store (see lib/snapshot-store.ts) with a pluggable
 * backend. When no baseline is available the endpoint reports that
 * honestly rather than pretending nothing changed.
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
  sourceKey,
} from "@/lib/data-source";
import { computeChanges } from "@/lib/rule-engine";
import type { ScoredTask } from "@/lib/types";
import {
  loadBaseline,
  saveBaseline,
  type Baseline,
} from "@/lib/snapshot-store";

export async function GET(request: Request) {
  const { params } = readParams(request);
  const source = sourceFromParams(params);

  try {
    const resolved = await resolveData(source);
    if (resolved.pending) {
      return fail("mapping_required", "This data source needs mapping.", 422, resolved.pending);
    }

    const filters = filtersFromParams(params);
    const filtered = applyFilters(resolved.tasks, filters);
    const key = sourceKey(source);

    const baseline = await loadBaseline(key);
    const changes = computeChanges(
      filtered,
      baseline ? (baseline.tasks as unknown as ScoredTask[]) : null,
    );

    const hasBaseline = baseline !== null;
    const meaningful =
      changes.new_overdue.length > 0 ||
      changes.newly_blocked.length > 0 ||
      changes.resolved.length > 0 ||
      changes.status_changes.length > 0 ||
      changes.new_decisions.length > 0;

    // Only advance the baseline when the data actually moved.
    if (!hasBaseline || baseline.fingerprint !== fingerprintOf(filtered)) {
      await saveBaseline(key, toBaseline(filtered));
    }

    return ok(
      {
        changes,
        total: meaningful
          ? changes.new_overdue.length +
            changes.newly_blocked.length +
            changes.resolved.length +
            changes.status_changes.length +
            changes.new_decisions.length
          : 0,
        hasBaseline,
        /** True when there is no previous state to compare against yet. */
        isFirstRun: !hasBaseline,
      },
      {
        source: resolved.source,
        total: resolved.tasks.length,
        filtered: filtered.length,
        referenceDate: new Date(resolved.referenceMs).toISOString(),
        warnings: hasBaseline
          ? undefined
          : ["No previous snapshot yet — showing an empty change set. Changes appear after the next refresh."],
      },
    );
  } catch (error) {
    return fail(
      "data_error",
      error instanceof Error ? error.message : "Failed to load data",
      400,
    );
  }
}

/** Stable fingerprint of the state change detection cares about. */
function fingerprintOf(tasks: ScoredTask[]): string {
  const columns = [
    "Task_ID",
    "Status",
    "Due_Date",
    "Last_Updated",
    "Executive_Decision_Required",
    "Blocker",
  ] as const;

  const parts = tasks
    .slice()
    .sort((a, b) => a.Task_ID.localeCompare(b.Task_ID))
    .map((task) =>
      columns.map((column) => String(task[column] ?? "")).join("|"),
    );
  // FNV-1a — small, fast, and stable across runtimes.
  let hash = 0x811c9dc5;
  const text = parts.join("\n");
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16);
}

function toBaseline(tasks: ScoredTask[]): Baseline {
  return {
    fingerprint: fingerprintOf(tasks),
    savedAt: new Date().toISOString(),
    tasks: tasks.map((task) => ({
      Task_ID: String(task.Task_ID ?? ""),
      Status: String(task.Status ?? ""),
      Due_Date: String(task.Due_Date ?? ""),
      Last_Updated: String(task.Last_Updated ?? ""),
      Executive_Decision_Required: task.Executive_Decision_Required === true,
      Blocker: String(task.Blocker ?? ""),
      overdue: task.overdue === true,
      blocked: task.blocked === true,
      decision_required: task.decision_required === true,
    })),
  };
}
