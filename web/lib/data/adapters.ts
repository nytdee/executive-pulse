/**
 * Executive Pulse — source adapters.
 *
 * Every data source implements one contract:
 *
 *     fetch() -> RawTable
 *
 * A RawTable is untyped rows plus their column names. The mapping layer
 * then translates whatever the source calls things onto the canonical
 * Executive Pulse schema. That means a new source never touches the
 * engine, the scoring or the UI.
 *
 * Implemented adapters:
 *   - sample      the bundled demo dataset
 *   - sheet       a published Google Sheet
 *   - upload      a CSV or XLSX file supplied by the user
 *
 * To add a source, implement SourceAdapter and register it. Nothing else
 * changes.
 */

import { loadGoogleSheet, parseCsv } from "./loader";
import { buildSampleTasks } from "./sample";
import type { RawTable } from "./schema";

export interface SourceAdapter {
  /** Stable identifier used in URLs and the session. */
  readonly id: string;
  /** Human-readable name shown in the UI. */
  readonly label: string;
  /** What kind of source this is, for UI grouping. */
  readonly kind: "built-in" | "file" | "remote";
  /**
   * Whether this adapter needs the user's browser (for local file
   * parsing) or can run entirely on the server.
   */
  readonly execution: "server" | "client";
  /**
   * Produce the raw table. May throw a DataValidationError with a
   * message intended for the user.
   */
  fetch(): Promise<RawTable>;
}

/* ------------------------------------------------------------------ */
/* Sample                                                              */
/* ------------------------------------------------------------------ */

export class SampleAdapter implements SourceAdapter {
  readonly id = "sample";
  readonly label = "Sample data";
  readonly kind = "built-in" as const;
  readonly execution = "server" as const;

  constructor(private readonly config: { referenceMs?: number } = {}) {}

  async fetch(): Promise<RawTable> {
    const reference =
      this.config.referenceMs === undefined
        ? new Date()
        : new Date(this.config.referenceMs);
    const tasks = buildSampleTasks(reference);
    return {
      columns: Object.keys(tasks[0] ?? {}),
      rows: tasks.map((task) =>
        Object.fromEntries(
          Object.entries(task).map(([key, value]) => [
            key,
            value === null || value === undefined ? "" : String(value),
          ]),
        ),
      ),
    };
  }
}

/* ------------------------------------------------------------------ */
/* Google Sheet                                                        */
/* ------------------------------------------------------------------ */

export interface SheetAdapterConfig {
  sheetId: string;
  gid?: string;
}

export class GoogleSheetAdapter implements SourceAdapter {
  readonly id = "sheet";
  readonly label = "Google Sheet";
  readonly kind = "remote" as const;
  readonly execution = "server" as const;

  constructor(private readonly config: SheetAdapterConfig) {}

  async fetch(): Promise<RawTable> {
    return loadGoogleSheet(this.config.sheetId, this.config.gid ?? "0");
  }
}

/* ------------------------------------------------------------------ */
/* Uploaded file                                                       */
/* ------------------------------------------------------------------ */

export interface UploadAdapterConfig {
  /** The file's text content. For CSV this is the raw text. */
  csv: string;
  /** Parsed XLSX rows, when the file is a workbook. */
  xlsx?: RawTable;
  fileName?: string;
}

export class UploadAdapter implements SourceAdapter {
  readonly id = "upload";
  readonly label = "Uploaded file";
  readonly kind = "file" as const;
  readonly execution = "client" as const;

  constructor(private readonly config: UploadAdapterConfig) {}

  async fetch(): Promise<RawTable> {
    if (this.config.xlsx) return this.config.xlsx;
    return parseCsv(this.config.csv);
  }
}
