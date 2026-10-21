/**
 * POST /api/v1/mapping — map a foreign sheet onto the canonical schema.
 *
 * Two modes:
 *   action=preview  -> returns suggested column/value mappings
 *   action=apply    -> applies a mapping and returns the scored dataset
 *
 * Suggestions come from the AI mapper when one is configured
 * (AI_API_KEY / AI_API_BASE / AI_MODEL), and from the rule-based alias
 * table otherwise. Either way the human can correct every field
 * before it is applied.
 */

import { fail, ok, readParams } from "@/lib/api";
import { mapWithAi } from "@/lib/aiMapping.server";
import { parseCsv } from "@/lib/data/loader";
import {
  applyMapping,
  mappingStatus,
  processMappedTable,
  suggestColumnMapping,
  suggestValueMapping,
  findUnknownValues,
  type ColumnMapping,
  type ValueMapping,
} from "@/lib/data/mapping";
import { REQUIRED_COLUMNS } from "@/lib/data/schema";
import type { RawTable } from "@/lib/data/schema";
import { computeAllFlags, rankAttention } from "@/lib/rule-engine";

interface MappingRequest {
  csv?: string;
  table?: RawTable | null;
  columns?: ColumnMapping;
  values?: ValueMapping;
  action?: "preview" | "apply";
}

export async function POST(request: Request) {
  const { params } = readParams(request);

  let body: MappingRequest;
  try {
    body = (await request.json()) as MappingRequest;
  } catch {
    return fail("bad_request", "Request body must be JSON", 400);
  }

  let raw: RawTable;
  try {
    if (body.table && Array.isArray(body.table.columns)) {
      raw = body.table;
    } else if (body.csv) {
      raw = parseCsv(body.csv);
    } else {
      return fail("bad_request", "Provide a CSV or a parsed table", 400);
    }
  } catch (error) {
    return fail(
      "parse_error",
      error instanceof Error ? error.message : "Could not read the source",
      400,
    );
  }

  if (raw.columns.length === 0) {
    return fail("parse_error", "The source has no header row", 400);
  }

  if ((body.action ?? "preview") === "preview") {
    const status = mappingStatus(raw);
    const warnings: string[] = [];

    // The AI mapper reads the sheet's actual columns and values. The
    // rule-based table is the fallback when no key is configured, and
    // the backstop when the model is unsure.
    let suggestedColumns = status.columnMapping;
    let suggestedValues = status.suggestions;
    let mappedBy = "rules";

    try {
      const ai = await mapWithAi(raw);
      if (ai) {
        mappedBy = "ai";
        // The model's answer wins where it has evidence; anything it
        // left out keeps the rule-based suggestion.
        const merged: ColumnMapping = { ...status.columnMapping };
        for (const [target, source] of Object.entries(ai.columns)) {
          merged[target] = source;
        }
        for (const required of REQUIRED_COLUMNS) {
          if (!merged[required]) merged[required] = null;
        }
        suggestedColumns = merged;

        suggestedValues = { ...status.suggestions };
        for (const [column, translations] of Object.entries(ai.values)) {
          suggestedValues[column] = {
            ...(suggestedValues[column] ?? {}),
            ...translations,
          };
        }

        if (ai.note) warnings.push(`AI: ${ai.note}`);
      } else {
        warnings.push(
          "AI mapping is not configured (set AI_API_KEY). Using the built-in field alias table.",
        );
      }
    } catch (error) {
      warnings.push(
        `AI mapping was unavailable (${
          error instanceof Error ? error.message : "unknown error"
        }). Using the built-in field alias table.`,
      );
    }

    return ok(
      {
        columns: raw.columns,
        rows: raw.rows.length,
        suggestedColumns,
        unmapped: status.unmapped,
        unknownValues: status.unknowns,
        suggestedValues,
        mappedBy,
      },
      {
        source: "upload",
        total: raw.rows.length,
        filtered: raw.rows.length,
        referenceDate: new Date().toISOString(),
        warnings: warnings.length ? warnings : undefined,
      },
    );
  }

  if (!body.columns) {
    return fail("bad_request", "A column mapping is required to apply", 400);
  }

  try {
    const mapped = applyMapping(raw, body.columns, body.values ?? {});
    const tasks = rankAttention(
      computeAllFlags(processMappedTable(mapped), Date.now()),
    );
    return ok(
      { tasks, rows: tasks.length },
      {
        source: "upload",
        total: tasks.length,
        filtered: tasks.length,
        referenceDate: new Date().toISOString(),
      },
    );
  } catch (error) {
    return fail(
      "mapping_error",
      error instanceof Error ? error.message : "Mapping failed",
      422,
    );
  }
}
