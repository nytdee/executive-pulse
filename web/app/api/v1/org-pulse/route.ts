/**
 * GET /api/v1/org-pulse — department-level rollup.
 *
 * Counts, rates and a risk score that discriminates between
 * departments (an earlier formulation saturated every department at
 * 100 and made the ranking meaningless).
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
} from "@/lib/data-source";
import { getOrgPulseEnhanced } from "@/lib/intelligence";

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
    const departments = getOrgPulseEnhanced(filtered);

    return ok(
      { departments, total: departments.length },
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
