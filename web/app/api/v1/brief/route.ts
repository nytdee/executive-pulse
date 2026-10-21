/**
 * GET /api/v1/brief — an agenda-ready meeting brief.
 *
 * Compiles decisions, risks, blockers, systemic patterns and the
 * questions worth asking. The point: an executive can walk into a
 * meeting prepared in under 60 seconds.
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
} from "@/lib/data-source";
import { generateMeetingBrief } from "@/lib/intelligence";

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

    const focusDepartments = (params.get("department") ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const focusOwners = (params.get("owner") ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    const brief = generateMeetingBrief(filtered, {
      meetingName: params.get("name") ?? "Meeting brief",
      referenceMs: resolved.referenceMs,
      focusDepartments: focusDepartments.length ? focusDepartments : null,
      focusOwners: focusOwners.length ? focusOwners : null,
    });

    return ok(brief, {
      source: resolved.source,
      total: resolved.tasks.length,
      filtered: filtered.length,
      referenceDate: new Date(resolved.referenceMs).toISOString(),
    });
  } catch (error) {
    return fail(
      "data_error",
      error instanceof Error ? error.message : "Failed to load data",
      400,
    );
  }
}
