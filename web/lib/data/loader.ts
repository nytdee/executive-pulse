/**
 * Executive Pulse — data ingestion.
 *
 * Three sources: the bundled sample dataset, an uploaded CSV/XLSX file,
 * and a published Google Sheet. All three produce a RawTable, which the
 * schema layer validates and normalises.
 */

import { DataValidationError } from "./schema";
import type { RawRow, RawTable } from "./schema";

/** How long a fetched sheet is reused before it is refetched. */
export const SHEET_CACHE_SECONDS = 300;

/** Parse a CSV string into a table. Handles quoted fields and CRLF. */
export function parseCsv(text: string): RawTable {
  // Excel and Google Sheets both export a UTF-8 byte order mark. Left in
  // place it becomes part of the first column's name, which makes that
  // column invisible to the mapper.
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;

  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;

  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];

    if (inQuotes) {
      if (char === '"') {
        if (source[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      field = "";
      row = [];
    } else if (char === "\r") {
      // ignore; the \n handles the line break
    } else {
      field += char;
    }
  }

  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  if (rows.length === 0) return { columns: [], rows: [] };

  const columns = rows[0].map((col) => col.trim());
  const dataRows = rows.slice(1).filter((r) => r.some((cell) => cell.trim() !== ""));

  const records: RawRow[] = dataRows.map((cells) => {
    const record: RawRow = {};
    columns.forEach((col, index) => {
      record[col] = (cells[index] ?? "").trim();
    });
    return record;
  });

  return { columns, rows: records };
}

/** Accept a bare sheet id or a full URL. Returns the bare id. */
export function sanitizeSheetId(sheetId: string): string {
  const cleaned = (sheetId ?? "").trim().replace(/^["']|["']$/g, "");
  if (!cleaned) {
    throw new DataValidationError("Sheet ID is empty. Paste the ID from your sheet URL.");
  }
  const match = /\/spreadsheets\/d\/([A-Za-z0-9-_]+)/.exec(cleaned);
  if (match) return match[1];
  if (cleaned.includes("/") || cleaned.includes(" ") || cleaned.includes("?")) {
    throw new DataValidationError(
      "Sheet ID looks invalid. Paste only the ID from the URL: " +
        "https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
    );
  }
  return cleaned;
}

/** Normalise a tab id. Blank means the first tab. */
export function sanitizeGid(gid: string | number | null | undefined): string {
  const cleaned = String(gid ?? "").trim();
  if (!cleaned) return "0";
  if (!/^\d+$/.test(cleaned)) {
    throw new DataValidationError(
      `Tab ID '${cleaned}' is invalid. It must be digits only ` +
        "(find it at the end of your sheet URL: #gid=123456, or leave blank for the first tab).",
    );
  }
  return cleaned;
}

/**
 * Load a published Google Sheet as CSV.
 *
 * Two endpoints are tried: the strict export endpoint and the more
 * lenient gviz endpoint. If a specific tab is requested and missing,
 * the first tab is retried.
 *
 * The response is cached for five minutes. Operational data changes on
 * the order of hours, and refetching on every request is slow and
 * risks Google's rate limits.
 */
export async function loadGoogleSheet(
  sheetId: string,
  gid = "0",
): Promise<RawTable> {
  const id = sanitizeSheetId(sheetId);
  const tab = sanitizeGid(gid);

  const candidates: Array<{ name: string; url: string }> = [
    {
      name: "export",
      url: `https://docs.google.com/spreadsheets/d/${id}/export?format=csv&gid=${tab}`,
    },
    {
      name: "gviz",
      url: `https://docs.google.com/spreadsheets/d/${id}/gviz/tq?tqx=out:csv&headers=1&gid=${tab}`,
    },
  ];

  if (tab !== "0") {
    candidates.push(
      {
        name: "export-first-tab",
        url: `https://docs.google.com/spreadsheets/d/${id}/export?format=csv&gid=0`,
      },
      {
        name: "gviz-first-tab",
        url: `https://docs.google.com/spreadsheets/d/${id}/gviz/tq?tqx=out:csv&headers=1&gid=0`,
      },
    );
  }

  const failures: string[] = [];

  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate.url, {
        headers: { "User-Agent": "Executive-Pulse" },
        next: { revalidate: SHEET_CACHE_SECONDS },
      });
      if (!response.ok) {
        failures.push(`${candidate.name}: HTTP ${response.status}`);
        continue;
      }
      const text = await response.text();
      if (!text.trim()) {
        failures.push(`${candidate.name}: sheet returned empty data`);
        continue;
      }
      const table = parseCsv(text);
      if (table.columns.length < 2) {
        failures.push(`${candidate.name}: sheet returned no usable columns`);
        continue;
      }
      return table;
    } catch (error) {
      failures.push(
        `${candidate.name}: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  const joined = failures.join(" | ");
  if (joined.includes("404")) {
    throw new DataValidationError(
      "Google Sheet not found (404). Check the Sheet ID " +
        "(from https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit). " +
        "Also confirm sharing: either 'Anyone with the link' or File -> Share -> Publish to web -> CSV.",
    );
  }
  if (joined.toLowerCase().includes("empty")) {
    throw new DataValidationError(
      "Google Sheet appears empty or not published. " +
        "Go to File -> Share -> Publish to web -> Entire Document -> CSV, then click Publish.",
    );
  }
  throw new DataValidationError(
    "Google keeps rejecting the request (400) on every endpoint. Likely causes: " +
      "1) the Tab ID does not exist in this sheet - leave Tab ID blank to use the first tab; " +
      "2) the file is an uploaded Excel file, not a native Google Sheet (File -> Save as Google Sheets); " +
      "3) a Google Workspace policy blocks public export - also try File -> Share -> Publish to web -> CSV " +
      "in addition to link sharing.",
  );
}

/** Load a CSV file from a URL or string. */
export function loadCsvText(text: string): RawTable {
  return parseCsv(text);
}
