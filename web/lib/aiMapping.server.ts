/**
 * Executive Pulse — AI field mapping.
 *
 * A reporting sheet rarely uses the canonical column names, and rarely
 * uses the canonical status labels. Rather than guess from a fixed
 * alias list, the model reads the sheet's actual columns and sample
 * values and works out the mapping.
 *
 * The model only ever *translates labels*. It cannot change a score, a
 * weight or the ranking — those live in the rule engine and are not
 * reachable from here.
 *
 * Configuration follows the same convention as the rest of the
 * workspace:
 *
 *   AI_API_KEY    the key (or OPENAI_API_KEY)
 *   AI_API_BASE   e.g. https://api.openai.com/v1
 *   AI_MODEL      e.g. gpt-4o-mini
 *
 * Without a key the rule-based alias table is used instead, so the
 * product still works offline.
 */

import {
  OPTIONAL_COLUMNS,
  REQUIRED_COLUMNS,
  VALID_IMPACTS,
  VALID_PRIORITIES,
  VALID_STATUSES,
} from "./data/schema";
import type { RawTable } from "./data/schema";
import type { ColumnMapping, ValueMapping } from "./data/mapping";

export interface AiMappingConfig {
  configured: boolean;
  model: string;
  baseUrl: string;
}

export function aiMappingConfig(): AiMappingConfig {
  const apiKey = process.env.AI_API_KEY || process.env.OPENAI_API_KEY || "";
  return {
    configured: Boolean(apiKey),
    model: process.env.AI_MODEL || "gpt-4o-mini",
    baseUrl: (process.env.AI_API_BASE || "https://api.openai.com/v1").replace(
      /\/$/,
      "",
    ),
  };
}

/** The result of an AI mapping attempt. */
export interface AiMappingResult {
  columns: ColumnMapping;
  values: ValueMapping;
  /** A short note about anything the model was unsure about. */
  note: string;
}

const SYSTEM_PROMPT = `You map a spreadsheet's columns and cell labels onto a fixed schema for an executive attention tool.

You are given the sheet's column names and a sample of the values in each column. For each target field, choose the source column that holds it. For each source column, you may also translate its non-canonical cell values into the canonical vocabulary.

Rules:
- Only map a target field to a column you have actual evidence for. If no column plausibly holds a required field, omit that field entirely rather than guessing.
- Each source column may be used for at most one target field.
- Leave optional fields unmapped if the sheet has no equivalent. Do not invent data.
- Translate cell values only for Status, Priority and Impact, and only for values that are not already canonical.
- "Waiting for Decision" and "Pending Approval" are Blocked. "At Risk", "On Track" and "Stale" are In Progress. "Complete" and "Closed" are Done. "Cancelled" and "Paused" are On Hold.
- Return JSON only. No prose, no code fences.`;

function buildUserPrompt(table: RawTable): string {
  const samples: Record<string, string[]> = {};

  for (const column of table.columns) {
    const values: string[] = [];
    for (const row of table.rows) {
      const value = (row[column] ?? "").trim();
      if (value && !values.includes(value)) values.push(value);
      if (values.length >= 6) break;
    }
    samples[column] = values;
  }

  return [
    "Target schema — required fields:",
    REQUIRED_COLUMNS.join(", "),
    "",
    "Target schema — optional fields:",
    OPTIONAL_COLUMNS.join(", "),
    "",
    "Canonical Status values:",
    VALID_STATUSES.join(", "),
    "",
    "Canonical Priority values:",
    VALID_PRIORITIES.join(", "),
    "",
    "Canonical Impact values:",
    VALID_IMPACTS.join(", "),
    "",
    "The sheet's columns and sample values:",
    JSON.stringify(samples, null, 2),
    "",
    'Reply with JSON shaped like:',
    '{"columns":{"Task_ID":"source column name"},"values":{"Status":{"foreign label":"canonical value"}},"note":"optional short note"}',
  ].join("\n");
}

/** Pull a JSON object out of a model response. */
function parseJsonObject(content: string): Record<string, unknown> {
  const cleaned = content
    .trim()
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/, "")
    .trim();

  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1) {
    throw new Error("The model did not return a JSON object.");
  }

  return JSON.parse(cleaned.slice(start, end + 1)) as Record<string, unknown>;
}

/**
 * Ask the model to map a table onto the canonical schema.
 * Returns null when no key is configured, so the caller can fall back
 * to the rule-based mapping.
 */
export async function mapWithAi(
  table: RawTable,
): Promise<AiMappingResult | null> {
  const config = aiMappingConfig();
  if (!config.configured) return null;

  const apiKey = process.env.AI_API_KEY || process.env.OPENAI_API_KEY || "";

  const response = await fetch(`${config.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: config.model,
      temperature: 0,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: buildUserPrompt(table) },
      ],
    }),
    signal: AbortSignal.timeout(30_000),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(
      `AI mapping failed (${response.status}). ${body.slice(0, 200)}`,
    );
  }

  const payload = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  const content = payload.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("AI mapping returned an empty response.");
  }

  const parsed = parseJsonObject(content);
  return sanitiseResult(parsed, table);
}

/**
 * Validate the model's answer against the table before it is used.
 *
 * The model is a suggestion, not a source of truth: a column it
 * invented, or one that does not exist in the sheet, is discarded.
 */
export function sanitiseResult(
  parsed: Record<string, unknown>,
  table: RawTable,
): AiMappingResult {
  const sourceColumns = new Set(table.columns);
  const columns: ColumnMapping = {};
  const used = new Set<string>();

  const rawColumns = (parsed.columns ?? {}) as Record<string, unknown>;
  for (const target of [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS]) {
    const source = rawColumns[target];
    if (typeof source !== "string") continue;
    if (!sourceColumns.has(source)) continue;
    if (used.has(source)) continue;
    columns[target] = source;
    used.add(source);
  }

  // Only accept translations that map a label that actually occurs.
  const values: ValueMapping = {};
  const rawValues = (parsed.values ?? {}) as Record<string, unknown>;
  for (const [column, translations] of Object.entries(rawValues)) {
    if (!sourceColumns.has(column)) continue;
    if (typeof translations !== "object" || translations === null) continue;

    const actual = new Set(
      table.rows
        .map((row) => (row[column] ?? "").trim())
        .filter((value) => value !== ""),
    );

    const accepted: Record<string, string> = {};
    for (const [from, to] of Object.entries(
      translations as Record<string, unknown>,
    )) {
      if (typeof to !== "string") continue;
      if (!actual.has(from)) continue;
      accepted[from] = to;
    }
    if (Object.keys(accepted).length > 0) values[column] = accepted;
  }

  const note =
    typeof parsed.note === "string" ? parsed.note.slice(0, 280) : "";

  return { columns, values, note };
}
