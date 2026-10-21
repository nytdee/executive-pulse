/**
 * GET|POST /api/v1/tasks — the full operational dataset.
 *
 * GET  — public, query-parameter driven. Suitable for external
 *        consumers and for sources without credentials.
 * POST — accepts the source and filters as JSON. Use this when the
 *        source carries credentials (an API token) or a large payload,
 *        because nothing sensitive then appears in a URL.
 *
 * Query parameters (GET):
 *   source=sample|sheet|api   data source
 *   sheetId=<id>              Google Sheet id (when source=sheet)
 *   gid=<n>                   sheet tab (default 0)
 *   department=A,B            filter by department
 *   owner=A,B                 filter by owner
 *   status=A,B                filter by status
 *   priority=A,B              filter by priority
 *   search=<text>             full-text search
 *   minScore=<n>              minimum attention score
 *   limit=<n>                 cap returned rows
 */

import { fail, ok, readParams } from "@/lib/api";
import {
  applyFilters,
  filtersFromParams,
  resolveData,
  sourceFromParams,
  type DataSource,
} from "@/lib/data-source";
import { getCounts } from "@/lib/rule-engine";

interface TasksRequest {
  source?: DataSource;
  filters?: {
    departments?: string[];
    owners?: string[];
    statuses?: string[];
    priorities?: string[];
    search?: string;
    minScore?: number;
    dateField?: "Due_Date" | "Start_Date" | "Last_Updated";
    dateFrom?: string | null;
    dateTo?: string | null;
  };
  limit?: number;
}

async function respond(
  source: DataSource,
  filters: Parameters<typeof applyFilters>[1],
  limit: number,
) {
  const resolved = await resolveData(source);

  if (resolved.pending) {
    return fail(
      "mapping_required",
      "This data source needs to be mapped onto the Executive Pulse schema.",
      422,
      resolved.pending,
    );
  }

  const filtered = applyFilters(resolved.tasks, filters);
  const tasks = limit > 0 ? filtered.slice(0, limit) : filtered;

  return ok(
    {
      tasks,
      counts: getCounts(resolved.tasks),
      filteredCounts: getCounts(filtered),
    },
    {
      source: resolved.source,
      total: resolved.tasks.length,
      filtered: filtered.length,
      referenceDate: new Date(resolved.referenceMs).toISOString(),
    },
  );
}

export async function GET(request: Request) {
  const { params } = readParams(request);
  const source = sourceFromParams(params);

  try {
    const filters = filtersFromParams(params);
    const limitRaw = params.get("limit");
    const limit = limitRaw ? Number(limitRaw) : 0;
    return await respond(source, filters, limit);
  } catch (error) {
    return fail(
      "data_error",
      error instanceof Error ? error.message : "Failed to load data",
      400,
    );
  }
}

export async function POST(request: Request) {
  let body: TasksRequest;
  try {
    body = (await request.json()) as TasksRequest;
  } catch {
    return fail("bad_request", "Request body must be JSON", 400);
  }

  const source = body.source ?? { kind: "sample" };
  const filters = body.filters ?? {};
  const limit = body.limit ?? 0;

  try {
    return await respond(source, filters, limit);
  } catch (error) {
    return fail(
      "data_error",
      error instanceof Error ? error.message : "Failed to load data",
      400,
    );
  }
}
