/**
 * Executive Pulse — XLSX parsing.
 *
 * Excel workbooks are parsed in the browser, so a file never has to be
 * uploaded to a server to be scored.
 *
 * Every sheet in the workbook is read. The sheet with the most data is
 * offered as the default, because reporting exports often put a
 * summary or a chart sheet first.
 */

import readXlsxFile, { type Row, type Sheet } from "read-excel-file/browser";

import type { RawTable } from "./schema";

export interface SheetInfo {
  name: string;
  rows: number;
  columns: number;
}

/** Describe each sheet in a workbook. */
export async function listSheets(file: File): Promise<SheetInfo[]> {
  const sheets: Sheet[] = await readXlsxFile(file);
  return sheets.map((sheet) => ({
    name: sheet.sheet,
    rows: Math.max(0, sheet.data.length - 1),
    columns: sheet.data[0]?.length ?? 0,
  }));
}

/**
 * Parse an XLSX file into a RawTable.
 *
 * @param file    the workbook
 * @param sheetName  which sheet to use; defaults to the largest
 */
export async function parseXlsx(
  file: File,
  sheetName?: string,
): Promise<RawTable> {
  const sheets: Sheet[] = await readXlsxFile(file);
  if (sheets.length === 0) {
    throw new Error("That workbook has no sheets.");
  }

  const chosen = sheetName
    ? (sheets.find((sheet) => sheet.sheet === sheetName) ?? sheets[0])
    : [...sheets].sort(
        (a, b) => (b.data?.length ?? 0) - (a.data?.length ?? 0),
      )[0];

  return rowsToTable(chosen.data ?? []);
}

/** Convert a grid of cells into a RawTable. */
export function rowsToTable(grid: Row[]): RawTable {
  const rows = grid.filter((row) =>
    row.some(
      (cell) =>
        cell !== null && cell !== undefined && String(cell).trim() !== "",
    ),
  );

  if (rows.length === 0) {
    throw new Error("That sheet has no data.");
  }

  const header = rows[0].map((cell, index) => {
    const text = cell === null || cell === undefined ? "" : String(cell).trim();
    return text || `Column ${index + 1}`;
  });

  const dataRows = rows.slice(1).map((row) => {
    const record: Record<string, string> = {};
    header.forEach((column, index) => {
      const cell = row[index];
      record[column] =
        cell === null || cell === undefined ? "" : String(cell).trim();
    });
    return record;
  });

  return { columns: header, rows: dataRows };
}
