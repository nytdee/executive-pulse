/**
 * Source adapter tests.
 *
 * Every data source must produce the same shape of output, so the
 * engine and UI never need to know which one was used.
 */

import { describe, expect, it } from "vitest";

import { SampleAdapter, UploadAdapter } from "@/lib/data/adapters";
import { parseCsv } from "@/lib/data/loader";
import { mappingStatus, suggestColumnMapping } from "@/lib/data/mapping";
import { loadAndValidate } from "@/lib/data/schema";
import { computeAllFlags, rankAttention } from "@/lib/rule-engine";

const CANONICAL_CSV = `Task_ID,Task,Project,Department,Owner,Status,Priority,Due_Date,Impact,Last_Updated,Executive_Decision_Required
X-1,Rebrand the site,Brand,Design,Priya,In Progress,High,2099-12-31,High,2099-12-30 09:00,Yes
X-2,Ship the campaign,Campaign,Marketing,Dev,Blocked,Critical,2099-12-31,Critical,2099-12-30 09:00,No`;

describe("sample adapter", () => {
  it("produces a table that validates and scores", async () => {
    const table = await new SampleAdapter().fetch();
    expect(table.columns.length).toBeGreaterThan(10);
    expect(table.rows.length).toBe(30);

    const tasks = loadAndValidate(table);
    const scored = rankAttention(computeAllFlags(tasks, Date.now()));
    expect(scored.length).toBe(30);
    expect(scored.some((task) => task.decision_required)).toBe(true);
  });

  it("is canonical, so it needs no mapping", async () => {
    const table = await new SampleAdapter().fetch();
    const { columnMapping, unmapped, unknowns } = mappingStatus(table);
    expect(unmapped).toEqual([]);
    expect(Object.keys(unknowns)).toEqual([]);
    for (const required of Object.keys(columnMapping)) {
      expect(columnMapping[required]).toBeTruthy();
    }
  });
});

describe("upload adapter", () => {
  it("parses a CSV into a table", async () => {
    const table = await new UploadAdapter({ csv: CANONICAL_CSV }).fetch();
    expect(table.columns).toContain("Task_ID");
    expect(table.rows.length).toBe(2);
  });

  it("accepts a pre-parsed table (from an XLSX file)", async () => {
    const parsed = parseCsv(CANONICAL_CSV);
    const table = await new UploadAdapter({ csv: "", xlsx: parsed }).fetch();
    expect(table.rows.length).toBe(2);
  });

  it("scores identically to the same data from any other source", async () => {
    const table = await new UploadAdapter({ csv: CANONICAL_CSV }).fetch();
    const tasks = loadAndValidate(table);
    const scored = rankAttention(computeAllFlags(tasks, Date.now()));

    expect(scored[0].Task_ID).toBe("X-2");
    expect(scored[0].blocked).toBe(true);
    expect(scored[0].attention_score).toBe(9); // critical impact 5 + blocked 4
    expect(scored[1].decision_required).toBe(true);
  });

  it("strips a UTF-8 byte order mark from the first column", async () => {
    // Excel exports a BOM. Left in, it becomes part of the first
    // column's name and the column becomes invisible to the mapper.
    const withBom = `\uFEFF${CANONICAL_CSV}`;
    const table = await new UploadAdapter({ csv: withBom }).fetch();
    expect(table.columns[0]).toBe("Task_ID");
    expect(table.columns).not.toContain("\uFEFFTask_ID");
  });
});

describe("column mapping across sources", () => {
  it("maps a CRM's column names onto the schema", () => {
    const { mapping } = suggestColumnMapping([
      "id",
      "title",
      "team",
      "assignee",
      "state",
      "due",
      "impact",
      "updated_at",
      "needs_decision",
    ]);
    expect(mapping.Task_ID).toBe("id");
    expect(mapping.Task).toBe("title");
    expect(mapping.Department).toBe("team");
    expect(mapping.Owner).toBe("assignee");
    expect(mapping.Status).toBe("state");
    expect(mapping.Due_Date).toBe("due");
    expect(mapping.Last_Updated).toBe("updated_at");
  });

  it("accepts true/false/1/0 for the decision flag without prompting", () => {
    const table = parseCsv(
      "Task_ID,Task,Project,Department,Owner,Status,Priority,Due_Date,Impact,Last_Updated,Executive_Decision_Required\n" +
        "X-1,Task,Proj,Design,Priya,In Progress,High,2099-12-31,High,2099-12-30 09:00,true\n" +
        "X-2,Task,Proj,Design,Priya,In Progress,High,2099-12-31,High,2099-12-30 09:00,FALSE\n" +
        "X-3,Task,Proj,Design,Priya,In Progress,High,2099-12-31,High,2099-12-30 09:00,1\n",
    );
    const { unknowns } = mappingStatus(table);
    expect(Object.keys(unknowns)).toEqual([]);
  });

  it("still prompts for a genuinely unrecognised decision label", () => {
    const table = parseCsv(
      "Task_ID,Task,Project,Department,Owner,Status,Priority,Due_Date,Impact,Last_Updated,Executive_Decision_Required\n" +
        "X-1,Task,Proj,Design,Priya,In Progress,High,2099-12-31,High,2099-12-30 09:00,maybe\n",
    );
    const { unknowns } = mappingStatus(table);
    expect(unknowns.Executive_Decision_Required).toEqual(["maybe"]);
  });

  it("flags a foreign status label for translation", () => {
    // This is what the real reporting sheet looks like.
    const table = parseCsv(
      "Task_ID,Task,Project,Department,Owner,Status,Priority,Due_Date,Impact,Last_Updated,Executive_Decision_Required\n" +
        "EP-001,Approve Q4 budget,Q4 Growth Plan,Marketing,Priya,Waiting for Decision,Critical,2026-09-29,Critical,2026-09-28 9:15,Yes\n",
    );
    const { unknowns } = mappingStatus(table);
    expect(unknowns.Status).toEqual(["Waiting for Decision"]);
  });
});
