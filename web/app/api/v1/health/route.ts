/**
 * GET /api/v1/health — service and data health.
 *
 * Useful for uptime checks and for confirming a deployed instance is
 * actually reaching its data source.
 */

import { fail, ok, readParams } from "@/lib/api";
import { resolveData, sourceFromParams } from "@/lib/data-source";
import { getCounts } from "@/lib/rule-engine";

export async function GET(request: Request) {
  const { params } = readParams(request);
  const source = sourceFromParams(params);
  const started = Date.now();

  try {
    const resolved = await resolveData(source);
    const counts = resolved.pending ? null : getCounts(resolved.tasks);

    return ok(
      {
        status: "ok",
        version: process.env.npm_package_version ?? "1.0.0",
        dataSource: resolved.source,
        rows: resolved.tasks.length,
        counts,
        needsMapping: resolved.pending !== null,
        latencyMs: Date.now() - started,
      },
      {
        source: resolved.source,
        total: resolved.tasks.length,
        filtered: resolved.tasks.length,
        referenceDate: new Date(resolved.referenceMs).toISOString(),
        warnings: resolved.pending
          ? ["Data source requires schema mapping before it can be scored."]
          : undefined,
      },
    );
  } catch (error) {
    return fail(
      "data_error",
      error instanceof Error ? error.message : "Failed to reach the data source",
      503,
    );
  }
}
