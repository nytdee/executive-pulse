/**
 * AI field-mapping tests.
 *
 * The model is a suggestion, not a source of truth. These tests pin
 * the guardrails: it may not invent a column, reuse a column, or
 * translate a label that does not occur in the data.
 */

import { describe, expect, it } from "vitest";

import { sanitiseResult } from "@/lib/aiMapping.server";
import { parseCsv } from "@/lib/data/loader";
import type { RawTable } from "@/lib/data/schema";

const REAL_SHEET = `Task_ID,Task,Project,Department,Owner,Owner_Role,Status,Priority,Start_Date,Due_Date,Completed_Date,Impact,Impact_Value,Blocker,Dependency,Blocker_Owner,Last_Updated,Executive_Decision_Required,Decision_By,Decision_Requested,Source_URL,Notes
"EP-001","Approve Q4 performance marketing budget","Q4 Growth Plan","Marketing","Priya Sharma","Head of Marketing","Waiting for Decision","Critical","2026-09-23","2026-09-29","","Critical","450000","","EP-006","","2026-09-28 9:15","Yes","2026-09-29","Approve Rs 4.5L incremental Q4 budget","","Campaign launch depends on budget approval."
"EP-002","Launch D2C festive campaign","Festive Growth Campaign","Marketing","Rohan Mehta","Growth Manager","At Risk","High","2026-09-18","2026-09-30","","High","850000","Creative approval pending","EP-004","Ananya Rao","2026-09-27 16:30","No","","","","Creative approval is holding final launch."`;

const table: RawTable = parseCsv(REAL_SHEET);

describe("AI mapping sanitiser", () => {
  it("accepts a column mapping that names real columns", () => {
    const result = sanitiseResult(
      {
        columns: { Task_ID: "Task_ID", Task: "Task", Department: "Department" },
        values: {},
      },
      table,
    );
    expect(result.columns.Task_ID).toBe("Task_ID");
    expect(result.columns.Task).toBe("Task");
    expect(result.columns.Department).toBe("Department");
  });

  it("discards a column the model invented", () => {
    const result = sanitiseResult(
      { columns: { Task_ID: "Task_ID", Task: "Nonexistent Column" }, values: {} },
      table,
    );
    expect(result.columns.Task_ID).toBe("Task_ID");
    expect(result.columns.Task).toBeUndefined();
  });

  it("discards a second target that claims the same source column", () => {
    const result = sanitiseResult(
      {
        columns: { Task_ID: "Task_ID", Task: "Task_ID", Project: "Project" },
        values: {},
      },
      table,
    );
    // The first target to claim a column keeps it.
    expect(result.columns.Task_ID).toBe("Task_ID");
    expect(result.columns.Task).toBeUndefined();
  });

  it("accepts a translation for a label that occurs in the data", () => {
    const result = sanitiseResult(
      {
        columns: {},
        values: { Status: { "Waiting for Decision": "Blocked" } },
      },
      table,
    );
    expect(result.values.Status?.["Waiting for Decision"]).toBe("Blocked");
  });

  it("discards a translation for a label that never occurs", () => {
    const result = sanitiseResult(
      {
        columns: {},
        values: { Status: { "Nonexistent Label": "Blocked" } },
      },
      table,
    );
    expect(result.values.Status).toBeUndefined();
  });

  it("discards translations for a column that is not in the sheet", () => {
    const result = sanitiseResult(
      {
        columns: {},
        values: { Nonexistent: { "Waiting for Decision": "Blocked" } },
      },
      table,
    );
    expect(result.values.Nonexistent).toBeUndefined();
  });

  it("ignores a non-string translation target", () => {
    const result = sanitiseResult(
      {
        columns: {},
        values: { Status: { "Waiting for Decision": 42 } },
      },
      table,
    );
    expect(result.values.Status).toBeUndefined();
  });

  it("keeps a short note and truncates a long one", () => {
    const short = sanitiseResult({ columns: {}, values: {}, note: "ok" }, table);
    expect(short.note).toBe("ok");

    const long = sanitiseResult(
      { columns: {}, values: {}, note: "x".repeat(1000) },
      table,
    );
    expect(long.note.length).toBeLessThanOrEqual(280);
  });

  it("survives a completely wrong response shape", () => {
    const result = sanitiseResult(
      { columns: "not an object", values: 42 },
      table,
    );
    expect(result.columns).toEqual({});
    expect(result.values).toEqual({});
    expect(result.note).toBe("");
  });
});

describe("AI mapping configuration", () => {
  it("reports unconfigured when there is no key", async () => {
    const { aiMappingConfig } = await import("@/lib/aiMapping.server");
    const previous = process.env.AI_API_KEY;
    const previousOpenAi = process.env.OPENAI_API_KEY;
    delete process.env.AI_API_KEY;
    delete process.env.OPENAI_API_KEY;

    try {
      expect(aiMappingConfig().configured).toBe(false);
    } finally {
      if (previous !== undefined) process.env.AI_API_KEY = previous;
      if (previousOpenAi !== undefined) process.env.OPENAI_API_KEY = previousOpenAi;
    }
  });

  it("uses the workspace's env conventions", async () => {
    const { aiMappingConfig } = await import("@/lib/aiMapping.server");
    const previousKey = process.env.AI_API_KEY;
    const previousBase = process.env.AI_API_BASE;
    const previousModel = process.env.AI_MODEL;

    process.env.AI_API_KEY = "test-key";
    process.env.AI_API_BASE = "https://example.test/v1/";
    process.env.AI_MODEL = "test-model";

    try {
      const config = aiMappingConfig();
      expect(config.configured).toBe(true);
      expect(config.baseUrl).toBe("https://example.test/v1");
      expect(config.model).toBe("test-model");
    } finally {
      if (previousKey === undefined) delete process.env.AI_API_KEY;
      else process.env.AI_API_KEY = previousKey;
      if (previousBase === undefined) delete process.env.AI_API_BASE;
      else process.env.AI_API_BASE = previousBase;
      if (previousModel === undefined) delete process.env.AI_MODEL;
      else process.env.AI_MODEL = previousModel;
    }
  });
});
