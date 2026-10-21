/**
 * GET /api/v1/blocked — where the organization is stuck.
 *
 * Grouped by blocker and by department, with cross-team friction
 * surfaced: who is blocking whom, for how long, and at what cost.
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
} from "@/lib/data-source";
import { getBlockedFrictionDetailed } from "@/lib/intelligence";

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
    const detail = getBlockedFrictionDetailed(filtered, resolved.referenceMs);

    return ok(
      {
        summary: detail.summary,
        byDepartment: detail.byDepartment,
        byBlockerOwner: detail.byBlockerOwner,
        crossTeam: detail.crossTeam,
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
