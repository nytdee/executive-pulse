/**
 * Executive Pulse — field mapping.
 *
 * Lets a user attach a sheet with arbitrary column names and value
 * labels ("Task ID" instead of "Task_ID", "Waiting for Decision" instead
 * of "Blocked") and map it onto the canonical schema.
 *
 * Mapping only translates labels. It never changes scoring, ranking or
 * validation rules.
 */

import {
  ALL_COLUMNS,
  DataValidationError,
  OPTIONAL_COLUMNS,
  REQUIRED_COLUMNS,
  VALID_DECISION_VALUES,
  VALID_IMPACTS,
  VALID_PRIORITIES,
  VALID_STATUSES,
  loadAndValidate,
  normalizeHeader,
} from "./schema";
import type { RawRow, RawTable } from "./schema";
import type { Task } from "@/lib/types";

/** Canonical key -> schema column. Covers common real-world variants. */
export const COLUMN_ALIASES: Record<string, string> = {
  taskid: "Task_ID", taskno: "Task_ID", id: "Task_ID", key: "Task_ID",
  task: "Task", taskname: "Task", title: "Task", workitem: "Task",
  name: "Task", summary: "Task", subject: "Task",
  project: "Project", program: "Project", initiative: "Project",
  epic: "Project", campaign: "Project", workstream: "Project",
  department: "Department", dept: "Department", team: "Department",
  function: "Department",
  owner: "Owner", ownername: "Owner", assignee: "Owner",
  responsible: "Owner", lead: "Owner", accountable: "Owner",
  ownerrole: "Owner_Role", role: "Owner_Role", ownerfunction: "Owner_Role",
  title_role: "Owner_Role",
  status: "Status", state: "Status", stage: "Status",
  priority: "Priority", prio: "Priority", urgency: "Priority",
  startdate: "Start_Date", start: "Start_Date", startdated: "Start_Date",
  duedate: "Due_Date", due: "Due_Date", deadline: "Due_Date",
  targetdate: "Due_Date", enddate: "Due_Date",
  completeddate: "Completed_Date", donedate: "Completed_Date",
  completed: "Completed_Date", closedate: "Completed_Date",
  finishdate: "Completed_Date",
  impact: "Impact", severity: "Impact", criticality: "Impact",
  impactvalue: "Impact_Value", businessimpact: "Impact_Value",
  value: "Impact_Value", arr: "Impact_Value", revenueatrisk: "Impact_Value",
  amount: "Impact_Value",
  blocker: "Blocker", blockers: "Blocker", blockedby: "Blocker",
  blockingreason: "Blocker", impediment: "Blocker", blockreason: "Blocker",
  dependency: "Dependency", dependencies: "Dependency",
  dependson: "Dependency", depends: "Dependency", relieson: "Dependency",
  blockedtask: "Dependency",
  blockerowner: "Blocker_Owner", unblockowner: "Blocker_Owner",
  waitingon: "Blocker_Owner", blockedowner: "Blocker_Owner",
  lastupdated: "Last_Updated", updated: "Last_Updated",
  lastupdate: "Last_Updated", modified: "Last_Updated",
  lastmodified: "Last_Updated", updatedat: "Last_Updated",
  executivedecisionrequired: "Executive_Decision_Required",
  decisionrequired: "Executive_Decision_Required",
  needsexecdecision: "Executive_Decision_Required",
  execdecision: "Executive_Decision_Required",
  requiresdecision: "Executive_Decision_Required",
  decisionneeded: "Executive_Decision_Required",
  decisionby: "Decision_By", decideby: "Decision_By",
  decisiondate: "Decision_By", decisiondeadline: "Decision_By",
  neededby: "Decision_By",
  decisionrequested: "Decision_Requested",
  decision: "Decision_Requested",
  approvalneeded: "Decision_Requested",
  sourceurl: "Source_URL", link: "Source_URL", url: "Source_URL",
  sourcelink: "Source_URL", ticket: "Source_URL", jira: "Source_URL",
  notes: "Notes", note: "Notes", comments: "Notes",
  comment: "Notes", description: "Notes", details: "Notes",
  context: "Notes", remarks: "Notes",
};

/** Suggested canonical status for common foreign labels. */
export const STATUS_SUGGESTIONS: Record<string, string> = {
  "waiting for decision": "Blocked",
  "awaiting decision": "Blocked",
  "pending approval": "Blocked",
  "awaiting approval": "Blocked",
  "at risk": "In Progress",
  atrisk: "In Progress",
  "stale": "In Progress",
  "on track": "In Progress",
  todo: "Not Started",
  "to do": "Not Started",
  backlog: "Not Started",
  complete: "Done",
  completed: "Done",
  closed: "Done",
  cancelled: "On Hold",
  paused: "On Hold",
};

/**
 * Columns whose values may need translating, and the canonical values a
 * user can map *to*.
 */
export const VALUE_COLUMNS: Record<string, string[]> = {
  Status: [...VALID_STATUSES].sort(),
  Priority: [...VALID_PRIORITIES].sort(),
  Impact: [...VALID_IMPACTS].sort(),
  Executive_Decision_Required: ["Yes", "No"],
};

/**
 * Labels that are already canonical for a column, so they never need
 * a mapping step.
 *
 * This is deliberately wider than VALUE_COLUMNS: the schema accepts
 * `true`/`false`/`1`/`0` for the decision flag, so a sheet using those
 * must not be interrupted with a pointless mapping prompt.
 */
export const ACCEPTED_VALUES: Record<string, Set<string>> = {
  Status: new Set(VALID_STATUSES.map((v) => v.toLowerCase())),
  Priority: new Set(VALID_PRIORITIES.map((v) => v.toLowerCase())),
  Impact: new Set(VALID_IMPACTS.map((v) => v.toLowerCase())),
  Executive_Decision_Required: new Set(
    [...VALID_DECISION_VALUES].map((v) => String(v).toLowerCase()),
  ),
};

export type ColumnMapping = Record<string, string | null>;
export type ValueMapping = Record<string, Record<string, string>>;

/** Suggest a schema<-uploaded mapping. */
export function suggestColumnMapping(
  uploadedColumns: string[],
): { mapping: ColumnMapping; unmapped: string[] } {
  const mapping: ColumnMapping = {};
  const used = new Set<string>();

  for (const schemaCol of [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS]) {
    if (uploadedColumns.includes(schemaCol) && !used.has(schemaCol)) {
      mapping[schemaCol] = schemaCol;
      used.add(schemaCol);
    }
  }

  for (const schemaCol of [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS]) {
    if (mapping[schemaCol]) continue;
    const candidate = uploadedColumns.find((col) => {
      if (used.has(col)) return false;
      return COLUMN_ALIASES[normalizeHeader(col)] === schemaCol;
    });
    if (candidate) {
      mapping[schemaCol] = candidate;
      used.add(candidate);
    }
  }

  for (const schemaCol of REQUIRED_COLUMNS) {
    if (!(schemaCol in mapping)) mapping[schemaCol] = null;
  }

  const unmapped = uploadedColumns.filter((col) => !used.has(col));
  return { mapping, unmapped };
}

/** Find value labels that are not canonical, after case-insensitive match. */
export function findUnknownValues(table: RawTable): Record<string, string[]> {
  const unknowns: Record<string, string[]> = {};
  for (const [col, valid] of Object.entries(VALUE_COLUMNS)) {
    if (!table.columns.includes(col)) continue;
    const allowed = ACCEPTED_VALUES[col] ?? new Set(valid.map((v) => v.toLowerCase()));
    const values = new Set<string>();
    for (const row of table.rows) {
      const value = (row[col] ?? "").trim();
      if (!value || ["nan", "none", "nat"].includes(value.toLowerCase())) continue;
      if (!allowed.has(value.toLowerCase())) values.add(value);
    }
    if (values.size > 0) unknowns[col] = [...values].sort();
  }
  return unknowns;
}

/** Prefill suggestions; the user can override every one. */
export function suggestValueMapping(
  unknowns: Record<string, string[]>,
): Record<string, Record<string, string>> {
  const suggestions: Record<string, Record<string, string>> = {};
  for (const [col, values] of Object.entries(unknowns)) {
    const perValue: Record<string, string> = {};
    for (const value of values) {
      if (col === "Status") {
        perValue[value] =
          STATUS_SUGGESTIONS[value.trim().toLowerCase()] ?? "In Progress";
      } else if (col === "Executive_Decision_Required") {
        const lowered = value.trim().toLowerCase();
        perValue[value] = ["yes", "y", "true", "1"].includes(lowered) ? "Yes" : "No";
      } else {
        perValue[value] = VALUE_COLUMNS[col][0];
      }
    }
    suggestions[col] = perValue;
  }
  return suggestions;
}

/**
 * Rename columns and translate labels.
 * Raises when two schema columns would read from the same source column.
 */
export function applyMapping(
  table: RawTable,
  columnMapping: ColumnMapping,
  valueMapping: ValueMapping,
): RawTable {
  const seen = new Map<string, string>();
  for (const [schemaCol, uploadedCol] of Object.entries(columnMapping)) {
    if (!uploadedCol) continue;
    if (seen.has(uploadedCol)) {
      throw new DataValidationError(
        `Columns '${seen.get(uploadedCol)}' and '${schemaCol}' both map from '${uploadedCol}'. Each sheet column can map to one field only.`,
      );
    }
    seen.set(uploadedCol, schemaCol);
  }

  const columns = table.columns.map(
    (col) => seen.get(col) ?? col,
  );

  const rows: RawRow[] = table.rows.map((row) => {
    const next: RawRow = {};
    for (const [col, value] of Object.entries(row)) {
      next[seen.get(col) ?? col] = value;
    }
    return next;
  });

  // Case-insensitive auto-normalisation for known labels.
  for (const [col, valid] of Object.entries(VALUE_COLUMNS)) {
    if (!columns.includes(col)) continue;
    const canonical = new Map(
      valid.map((v) => [v.toLowerCase(), v] as const),
    );
    for (const row of rows) {
      const raw = (row[col] ?? "").trim();
      if (!raw) continue;
      row[col] = canonical.get(raw.toLowerCase()) ?? raw;
    }
  }

  // User-directed translations.
  for (const [col, translations] of Object.entries(valueMapping ?? {})) {
    if (!columns.includes(col) || !translations) continue;
    for (const row of rows) {
      const current = (row[col] ?? "").trim();
      if (translations[current]) row[col] = translations[current];
    }
  }

  return { columns, rows };
}

/** Validate, normalise and score a mapped table. */
export function processMappedTable(table: RawTable): Task[] {
  return loadAndValidate(table);
}

/** Inspect a raw table: mapping, unmapped columns, unknown values. */
export function mappingStatus(table: RawTable): {
  columnMapping: ColumnMapping;
  unmapped: string[];
  unknowns: Record<string, string[]>;
  suggestions: Record<string, Record<string, string>>;
} {
  const { mapping, unmapped } = suggestColumnMapping(table.columns);
  const renamedColumns = table.columns.map((col) => mapping[col] ?? col);
  const renamed: RawTable = {
    columns: renamedColumns,
    rows: table.rows.map((row) => {
      const next: RawRow = {};
      for (const [col, value] of Object.entries(row)) {
        next[mapping[col] ?? col] = value;
      }
      return next;
    }),
  };
  const unknowns = findUnknownValues(renamed);
  const suggestions = suggestValueMapping(unknowns);
  return { columnMapping: mapping, unmapped, unknowns, suggestions };
}
