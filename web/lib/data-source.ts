/**
 * Executive Pulse — data source resolution.
 *
 * A single place that turns "where is the data coming from" into a
 * scored dataset. Every API route and every page goes through here, so
 * the web app and the API can never disagree.
 */

import { cache } from "react";
import { connection } from "next/server";

import { mapWithAi } from "./aiMapping.server";
import {
  GoogleSheetAdapter,
  SampleAdapter,
  UploadAdapter,
  type SourceAdapter,
} from "./data/adapters";
import {
  applyMapping,
  findUnknownValues,
  mappingStatus,
  processMappedTable,
  type ColumnMapping,
  type ValueMapping,
} from "./data/mapping";
import { loadAndValidate, type RawTable } from "./data/schema";
import { computeAllFlags, rankAttention } from "./rule-engine";
import type { ScoredTask, Task } from "./types";

export type DataSourceKind = "sample" | "sheet" | "upload";

export interface DataSource {
  kind: DataSourceKind;
  sheetId?: string;
  gid?: string;
  csv?: string;
  /** Parsed XLSX rows, when the file is a workbook. */
  xlsx?: RawTable;
  fileName?: string;
  /** A confirmed column/value mapping for foreign sheets. */
  mapping?: { columns: ColumnMapping; values: ValueMapping };
}

export interface ResolvedData {
  tasks: ScoredTask[];
  /** Present when the raw table needs a human to complete the mapping. */
  pending: {
    columns: string[];
    rows: number;
    suggestedColumns: ColumnMapping;
    unmapped: string[];
    unknownValues: Record<string, string[]>;
    suggestedValues: Record<string, Record<string, string>>;
  } | null;
  referenceMs: number;
  source: string;
}

/** A stable key describing the active source, used for caching. */
export function sourceKey(source: DataSource): string {
  if (source.kind === "sheet") {
    return `sheet:${source.sheetId ?? ""}:${source.gid ?? "0"}`;
  }
  if (source.kind === "upload") {
    return `upload:${(source.csv ?? "").length}:${hashText(source.csv ?? "")}`;
  }
  return "sample";
}

function hashText(text: string): string {
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) + hash + text.charCodeAt(i)) >>> 0;
  }
  return hash.toString(36);
}

/**
 * Build the adapter for a source. Every source funnels through this,
 * so a new source only needs an adapter — never engine or UI changes.
 */
export function adapterFor(source: DataSource, referenceMs?: number): SourceAdapter {
  switch (source.kind) {
    case "sheet":
      return new GoogleSheetAdapter({
        sheetId: source.sheetId ?? "",
        gid: source.gid ?? "0",
      });
    case "upload":
      return new UploadAdapter({
        csv: source.csv ?? "",
        xlsx: source.xlsx,
        fileName: source.fileName,
      });
    case "sample":
    default:
      return new SampleAdapter({ referenceMs });
  }
}

/** Read the raw table for a source, before any mapping is applied. */
export async function readRawTable(
  source: DataSource,
  referenceMs?: number,
): Promise<RawTable> {
  return adapterFor(source, referenceMs).fetch();
}

/**
 * Resolve a source into scored tasks.
 *
 * Foreign sheets are mapped automatically when the mapping is
 * unambiguous; otherwise a `pending` descriptor is returned so the UI
 * can ask the user to complete it.
 *
 * The reference clock is read at request time (never at build time), so
 * "today" is always the day the user is looking at it.
 */
export async function resolveData(
  source: DataSource,
  referenceMs?: number,
): Promise<ResolvedData> {
  if (referenceMs === undefined) {
    // Opt into request-time rendering: the dashboard is a live
    // operational view, never a build-time snapshot.
    await connection();
    referenceMs = Date.now();
  }

  const key = sourceKey(source);
  const raw = await readRawTable(source, referenceMs);

  if (source.mapping) {
    const mapped = applyMapping(raw, source.mapping.columns, source.mapping.values);
    return {
      tasks: rankAttention(computeAllFlags(processMappedTable(mapped), referenceMs)),
      pending: null,
      referenceMs,
      source: key,
    };
  }

  // The sample dataset is already canonical, so it skips the mapping
  // round-trip but still goes through the same validation and scoring.
  if (source.kind === "sample") {
    return {
      tasks: rankAttention(computeAllFlags(loadAndValidate(raw), referenceMs)),
      pending: null,
      referenceMs,
      source: key,
    };
  }

  const { columnMapping, unmapped, unknowns, suggestions } = mappingStatus(raw);

  // The AI mapper reads the sheet's actual columns and sample values.
  // It is used for every source, and the rule-based alias table is the
  // fallback when no key is configured.
  let resolvedColumns = columnMapping;
  let resolvedValues = suggestions;
  let mappedBy: "ai" | "rules" = "rules";

  try {
    const ai = await mapWithAi(raw);
    if (ai) {
      mappedBy = "ai";
      const merged: ColumnMapping = { ...columnMapping };
      for (const [target, source] of Object.entries(ai.columns)) {
        merged[target] = source;
      }
      resolvedColumns = merged;

      resolvedValues = { ...suggestions };
      for (const [column, translations] of Object.entries(ai.values)) {
        resolvedValues[column] = {
          ...(resolvedValues[column] ?? {}),
          ...translations,
        };
      }
    }
  } catch {
    // AI mapping is best-effort. The rule-based table still applies.
    mappedBy = "rules";
  }

  // Recompute the unknown-value set against the resolved columns, so
  // labels the model translated are no longer treated as unknown.
  const renamed: RawTable = {
    columns: raw.columns.map((col) => resolvedColumns[col] ?? col),
    rows: raw.rows.map((row) => {
      const next: Record<string, string> = {};
      for (const [col, value] of Object.entries(row)) {
        next[resolvedColumns[col] ?? col] = value;
      }
      return next;
    }),
  };
  const remainingUnknowns = findUnknownValues(renamed);

  const required = Object.entries(resolvedColumns).filter(
    ([schemaCol]) =>
      !Object.keys(raw.columns).some((c) => c === schemaCol) &&
      schemaCol !== "Status" &&
      schemaCol !== "Priority" &&
      schemaCol !== "Impact" &&
      schemaCol !== "Executive_Decision_Required" &&
      resolvedColumns[schemaCol] === null,
  );

  const needsUi = required.length > 0 || Object.keys(remainingUnknowns).length > 0;

  if (needsUi) {
    return {
      tasks: [],
      pending: {
        columns: raw.columns,
        rows: raw.rows.length,
        suggestedColumns: resolvedColumns,
        unmapped,
        unknownValues: remainingUnknowns,
        suggestedValues: resolvedValues,
      },
      referenceMs,
      source: key,
    };
  }

  // Automatic mapping — everything resolved cleanly.
  const autoColumns: ColumnMapping = {};
  for (const [schemaCol, uploaded] of Object.entries(resolvedColumns)) {
    if (uploaded) autoColumns[schemaCol] = uploaded;
  }
  const mapped = applyMapping(raw, autoColumns, resolvedValues);
  return {
    tasks: rankAttention(computeAllFlags(processMappedTable(mapped), referenceMs)),
    pending: null,
    referenceMs,
    source: key,
  };
}

/** Cached variant for server components. */
export const getResolvedData = cache(async (source: DataSource) =>
  resolveData(source),
);

/** Apply a filter set to a scored dataset. */
export function applyFilters(tasks: ScoredTask[], filters: {
  departments?: string[];
  owners?: string[];
  statuses?: string[];
  priorities?: string[];
  search?: string;
  minScore?: number;
  dateField?: "Due_Date" | "Start_Date" | "Last_Updated";
  dateFrom?: string | null;
  dateTo?: string | null;
}): ScoredTask[] {
  let result = tasks;

  if (filters.departments?.length) {
    result = result.filter((task) => filters.departments!.includes(task.Department));
  }
  if (filters.owners?.length) {
    result = result.filter((task) => filters.owners!.includes(task.Owner));
  }
  if (filters.statuses?.length) {
    result = result.filter((task) => filters.statuses!.includes(task.Status));
  }
  if (filters.priorities?.length) {
    result = result.filter((task) => filters.priorities!.includes(task.Priority));
  }
  if (filters.minScore && filters.minScore > 0) {
    result = result.filter((task) => task.attention_score >= filters.minScore!);
  }
  if (filters.search && filters.search.trim()) {
    const needle = filters.search.trim().toLowerCase();
    result = result.filter((task) =>
      [task.Task, task.Project, task.Owner, task.Blocker, task.Notes].some(
        (value) => (value ?? "").toLowerCase().includes(needle),
      ),
    );
  }
  if (filters.dateFrom || filters.dateTo) {
    const field = filters.dateField ?? "Due_Date";
    result = result.filter((task) => {
      const value = task[field];
      if (!value) return false;
      const stamp = new Date(value.length === 10 ? `${value}T00:00:00Z` : `${value.replace(" ", "T")}Z`).getTime();
      if (Number.isNaN(stamp)) return false;
      if (filters.dateFrom) {
        const from = new Date(`${filters.dateFrom}T00:00:00Z`).getTime();
        if (stamp < from) return false;
      }
      if (filters.dateTo) {
        const to = new Date(`${filters.dateTo}T00:00:00Z`).getTime();
        if (stamp > to) return false;
      }
      return true;
    });
  }

  return result;
}

/** Parse a query string into a filter set. */
export function filtersFromParams(params: URLSearchParams) {
  const list = (key: string): string[] =>
    (params.get(key) ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

  const minScoreRaw = params.get("minScore");
  const dateField = params.get("dateField") as
    | "Due_Date"
    | "Start_Date"
    | "Last_Updated"
    | null;

  return {
    departments: list("department"),
    owners: list("owner"),
    statuses: list("status"),
    priorities: list("priority"),
    search: params.get("search") ?? "",
    minScore: minScoreRaw ? Number(minScoreRaw) : 0,
    dateField: dateField ?? "Due_Date",
    dateFrom: params.get("dateFrom"),
    dateTo: params.get("dateTo"),
  };
}

/** Build a DataSource from request params. */
export function sourceFromParams(params: URLSearchParams): DataSource {
  const kind = (params.get("source") ?? "sample") as DataSourceKind;
  if (kind === "sheet") {
    return {
      kind: "sheet",
      sheetId: params.get("sheetId") ?? "",
      gid: params.get("gid") ?? "0",
    };
  }
  if (kind === "upload") {
    return { kind: "upload", csv: params.get("csv") ?? "" };
  }
  return { kind: "sample" };
}

export { loadAndValidate };
export type { Task };
