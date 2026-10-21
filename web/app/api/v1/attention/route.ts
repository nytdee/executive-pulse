/**
 * GET /api/v1/attention — the executive attention queue.
 *
 * Returns only Critical and High band items, ranked by the engine, with
 * the reason codes that explain why each item surfaced. The persona
 * lens and the focus profile group the queue; neither changes a score.
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
} from "@/lib/data-source";
import { extractProfileKeywords, groupByPersona, groupByProfile } from "@/lib/persona";
import { getExecutiveAttentionQueue } from "@/lib/rule-engine";

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

    const limitRaw = Number(params.get("limit") ?? 7);
    const band = (params.get("band") ?? "High") as "Critical" | "High" | "Watch" | "Normal";
    const queue = getExecutiveAttentionQueue(filtered, limitRaw, band);

    const persona = params.get("persona");
    const focus = params.get("focus");
    const keywords = focus ? extractProfileKeywords(focus) : [];

    const profileGroup = keywords.length > 0 ? groupByProfile(queue, keywords, limitRaw) : null;
    const personaGroup = profileGroup
      ? null
      : groupByPersona(queue, persona, limitRaw);

    return ok(
      {
        items: queue,
        grouping: profileGroup
          ? {
              mode: "focus" as const,
              keywords,
              forYou: profileGroup.mine,
              onRadar: profileGroup.rest,
              matches: Object.fromEntries(profileGroup.matches),
            }
          : personaGroup
            ? {
                mode: "persona" as const,
                persona,
                forYou: personaGroup.mine,
                onRadar: personaGroup.rest,
              }
            : { mode: "organization" as const, forYou: [], onRadar: queue },
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
