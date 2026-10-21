/**
 * Executive Pulse — schema, validation and normalisation.
 *
 * Mirrors `app/data/loader.py`. The canonical schema is fixed; foreign
 * sheets are mapped onto it (see mapping.ts) before validation runs.
 */

import type { Impact, Priority, Status, Task } from "@/lib/types";

export const REQUIRED_COLUMNS = [
  "Task_ID",
  "Task",
  "Project",
  "Department",
  "Owner",
  "Status",
  "Priority",
  "Due_Date",
  "Impact",
  "Last_Updated",
  "Executive_Decision_Required",
] as const;

export const OPTIONAL_COLUMNS = [
  "Owner_Role",
  "Start_Date",
  "Completed_Date",
  "Impact_Value",
  "Blocker",
  "Dependency",
  "Blocker_Owner",
  "Decision_By",
  "Decision_Requested",
  "Source_URL",
  "Notes",
] as const;

export const ALL_COLUMNS = [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS];

export const VALID_STATUSES: Status[] = [
  "Not Started",
  "In Progress",
  "Blocked",
  "Done",
  "On Hold",
  "Overdue",
];

export const VALID_PRIORITIES: Priority[] = ["Low", "Medium", "High", "Critical"];

export const VALID_IMPACTS: Impact[] = ["Low", "Medium", "High", "Critical"];

export const VALID_DECISION_VALUES = new Set([
  "Yes",
  "No",
  "True",
  "False",
  "true",
  "false",
  "1",
  "0",
  "y",
  "Y",
]);

export class DataValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DataValidationError";
  }
}

/** A raw row as read from CSV — every cell is a string. */
export type RawRow = Record<string, string>;

export type RawTable = {
  columns: string[];
  rows: RawRow[];
};

/** Normalise a header for fuzzy matching. */
export function normalizeHeader(name: string): string {
  return String(name ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

/** Parse a boolean-ish cell. */
export function parseBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (value === null || value === undefined) return false;
  const text = String(value).trim().toLowerCase();
  return text === "yes" || text === "true" || text === "1" || text === "y";
}

/** Parse a date cell into an ISO-ish string, or "" when unparseable. */
export function parseDateCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value).trim();
  if (!text) return "";

  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(text);
  if (iso) {
    const time = /[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(text);
    return time
      ? `${iso[0]} ${time[1]}:${time[2]}${time[3] ? `:${time[3]}` : ""}`
      : iso[0];
  }

  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toISOString().slice(0, 19).replace("T", " ");
}

/** Parse a numeric cell. */
export function parseNumberCell(value: unknown): number {
  if (value === null || value === undefined || value === "") return 0;
  const text = String(value).trim();
  const parsed = Number(text.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Validate that required columns are present. */
export function validateColumns(table: RawTable): {
  missing: string[];
  extra: string[];
} {
  const present = new Set(table.columns);
  const missing = REQUIRED_COLUMNS.filter((col) => !present.has(col));
  const extra = table.columns.filter(
    (col) => !(ALL_COLUMNS as readonly string[]).includes(col),
  );
  return { missing, extra };
}

/** Validate data quality. Returns a list of human-readable errors. */
export function validateData(table: RawTable): string[] {
  const errors: string[] = [];

  if (table.rows.length === 0) {
    errors.push("Dataset is empty");
    return errors;
  }

  const column = (name: string): string[] =>
    table.rows.map((row) => (row[name] ?? "").trim());

  const taskIds = column("Task_ID");
  const blankIds = taskIds.filter((id) => id === "").length;
  if (blankIds > 0) {
    errors.push(`Found ${blankIds} rows with blank Task_ID`);
  }

  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const id of taskIds) {
    if (id && seen.has(id)) duplicates.add(id);
    seen.add(id);
  }
  if (duplicates.size > 0) {
    errors.push(`Found duplicate Task_ID values: ${[...duplicates].join(", ")}`);
  }

  const invalid = (
    name: string,
    valid: readonly string[],
  ): string[] => {
    const allowed = new Set(valid.map((v) => v.toLowerCase()));
    const values = new Set(
      column(name)
        .filter((value) => value !== "")
        .filter((value) => !allowed.has(value.toLowerCase())),
    );
    return [...values];
  };

  const badStatus = invalid("Status", VALID_STATUSES);
  if (badStatus.length > 0) {
    errors.push(`Invalid Status values: ${badStatus.join(", ")}`);
  }

  const badPriority = invalid("Priority", VALID_PRIORITIES);
  if (badPriority.length > 0) {
    errors.push(`Invalid Priority values: ${badPriority.join(", ")}`);
  }

  const badImpact = invalid("Impact", VALID_IMPACTS);
  if (badImpact.length > 0) {
    errors.push(`Invalid Impact values: ${badImpact.join(", ")}`);
  }

  const badDecision = column("Executive_Decision_Required")
    .filter((value) => value !== "")
    .filter((value) => !VALID_DECISION_VALUES.has(value));
  if (badDecision.length > 0) {
    errors.push(
      `Invalid Executive_Decision_Required values: ${[...new Set(badDecision)].join(", ")}`,
    );
  }

  for (const name of [
    "Due_Date",
    "Start_Date",
    "Completed_Date",
    "Last_Updated",
    "Decision_By",
  ]) {
    if (!table.columns.includes(name)) continue;
    const values = column(name).filter((value) => value !== "");
    const unparseable = values.filter((value) => parseDateCell(value) === "");
    if (unparseable.length > 0) {
      errors.push(
        `Invalid date format in ${name}: ${[...new Set(unparseable)].slice(0, 5).join(", ")}`,
      );
    }
  }

  if (table.columns.includes("Impact_Value")) {
    const values = column("Impact_Value").filter((value) => value !== "");
    const nonNumeric = values.filter((value) => {
      const parsed = Number(value.replace(/[^0-9.\-]/g, ""));
      return !Number.isFinite(parsed);
    });
    if (nonNumeric.length > 0) {
      errors.push(
        `Non-numeric Impact_Value values: ${[...new Set(nonNumeric)].slice(0, 5).join(", ")}`,
      );
    }
  }

  return errors;
}

/**
 * Normalise a raw table into canonical tasks.
 * Fills optional columns, coerces types, and trims whitespace.
 */
export function normalizeData(table: RawTable): Task[] {
  return table.rows.map((row) => {
    const read = (name: string): string => (row[name] ?? "").trim();

    const status = read("Status") as Status;
    const priority = read("Priority") as Priority;
    const impact = read("Impact") as Impact;

    return {
      Task_ID: read("Task_ID"),
      Task: read("Task"),
      Project: read("Project"),
      Department: read("Department"),
      Owner: read("Owner"),
      Owner_Role: read("Owner_Role"),
      Status: status,
      Priority: priority,
      Start_Date: read("Start_Date") || null,
      Due_Date: read("Due_Date") || null,
      Completed_Date: read("Completed_Date") || null,
      Impact: impact,
      Impact_Value: parseNumberCell(read("Impact_Value")),
      Blocker: read("Blocker"),
      Dependency: read("Dependency"),
      Blocker_Owner: read("Blocker_Owner"),
      Last_Updated: read("Last_Updated") || null,
      Executive_Decision_Required: parseBoolean(read("Executive_Decision_Required")),
      Decision_By: read("Decision_By") || null,
      Decision_Requested: read("Decision_Requested"),
      Source_URL: read("Source_URL"),
      Notes: read("Notes"),
    };
  });
}

/** Validate and normalise in one step. */
export function loadAndValidate(table: RawTable): Task[] {
  const { missing } = validateColumns(table);
  if (missing.length > 0) {
    throw new DataValidationError(`Missing required columns: ${missing.join(", ")}`);
  }
  const errors = validateData(table);
  if (errors.length > 0) {
    throw new DataValidationError(errors.join("; "));
  }
  return normalizeData(table);
}
