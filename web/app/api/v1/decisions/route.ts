/**
 * GET /api/v1/decisions — the executive decision queue.
 *
 * Each entry states what decision is needed, who is waiting, when it is
 * needed and what it costs. This is the module that makes the product a
 * decision layer rather than a dashboard.
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
} from "@/lib/data-source";
import { getDecisionQueue } from "@/lib/rule-engine";
import { getDecisionQueueDetailed } from "@/lib/intelligence";

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
    const decisions = getDecisionQueueDetailed(filtered, resolved.referenceMs);

    return ok(
      {
        decisions,
        total: decisions.length,
      },
      {
        source: resolved.source,
        total: resolved.tasks.length,
        filtered: filtered.length,
        referenceDate: new Date(resolved.referenceMs).toISOString(),
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
