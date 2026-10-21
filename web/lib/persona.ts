/**
 * Executive Pulse — persona lens and freeform focus profile.
 *
 * Both features only *group* the engine ranking. They never change a
 * score, never re-order within a group, and never alter the underlying
 * rules. That guarantee is what makes them safe to expose.
 */

import { rankAttention } from "./rule-engine";
import type { ScoredTask } from "./types";

/** Departments in a viewer's scope. `null` means the whole organization. */
export const PERSONAS: Record<string, string[] | null> = {
  CEO: null,
  "Chief of Staff": null,
  CMO: ["Marketing", "Sales"],
  CFO: ["Finance", "Legal"],
  "CTO / CPO": ["Technology", "Product"],
  COO: ["Operations", "Technology", "People"],
};

export function personaDepartments(persona: string | null | undefined): string[] | null {
  if (!persona) return null;
  return PERSONAS[persona] ?? null;
}

/** Top engine-ranked open items inside the viewer's departments. */
export function personaRelevant(
  tasks: ScoredTask[],
  persona: string | null | undefined,
  maxItems = 3,
): ScoredTask[] {
  const departments = personaDepartments(persona);
  if (!departments) return [];
  const subset = tasks.filter(
    (task) => departments.includes(task.Department) && task.Status !== "Done",
  );
  return rankAttention(subset).slice(0, maxItems);
}

/**
 * Split the attention queue into "for you" and "also on your radar".
 * Order within each group is the engine ranking, untouched.
 */
export function groupByPersona(
  attention: ScoredTask[],
  persona: string | null | undefined,
  maxItems = 5,
): { mine: ScoredTask[]; rest: ScoredTask[] } {
  const departments = personaDepartments(persona);
  if (!departments) {
    return { mine: [], rest: attention.slice(0, maxItems) };
  }
  const mine = attention
    .filter((task) => departments.includes(task.Department))
    .slice(0, 3);
  const mineIds = new Set(mine.map((task) => task.Task_ID));
  const rest = attention
    .filter((task) => !mineIds.has(task.Task_ID))
    .slice(0, Math.max(0, maxItems - mine.length));
  return { mine, rest };
}

// ---------------------------------------------------------------------------
// Focus profile
// ---------------------------------------------------------------------------

const PROFILE_STOPWORDS = new Set(
  `i me my we our you your he she it they them his her its their
   am is are was were be been being have has had do does did will
   would can could should shall may might must a an the and or but
   of on in to for with as at by from that this these those then
   so such no not only also very include includes including things
   thing stuff priorities priority chief officer head like want need
   needs look looking tell show give get please hello hey`
    .split(/\s+/)
    .filter(Boolean),
);

/** field -> weight for one distinct keyword hit. */
export const PROFILE_FIELDS: Array<[string, number]> = [
  ["Task", 3],
  ["Project", 2],
  ["Department", 2],
  ["Decision_Requested", 2],
  ["Blocker", 1],
  ["Notes", 1],
  ["Owner", 1],
  ["Owner_Role", 1],
];

export const MAX_PROFILE_KEYWORDS = 12;

/** Split text into alphanumeric tokens, lowercased. */
export function normTokens(text: unknown): string[] {
  if (text === null || text === undefined) return [];
  return String(text)
    .split(/[^A-Za-z0-9]+/)
    .map((token) => token.toLowerCase().replace(/[^a-z0-9]/g, ""))
    .filter(Boolean);
}

/**
 * Prefix-tolerant match.
 *
 *   "launch"  matches "launches"     (token extends the keyword)
 *   "brand"   matches "rebranding"   (keyword inside a longer word)
 *   "design"  matches "designed"
 *
 * A keyword must never match a *shorter* token that merely shares its
 * prefix: "marketing" must not match "market", or a task titled
 * "India market launch" would land in a Marketing exec's queue.
 */
export function tokMatch(keyword: string, token: string): boolean {
  if (keyword.length < 3 || token.length < 3) return false;
  if (token === keyword) return true;
  if (token.startsWith(keyword)) return true;
  return keyword.length >= 5 && token.includes(keyword);
}

/** Meaningful keywords from freeform focus text, order preserved. */
export function extractProfileKeywords(text: string | null | undefined): string[] {
  const keywords: string[] = [];
  for (const token of normTokens(text)) {
    if (token.length < 2 || PROFILE_STOPWORDS.has(token)) continue;
    if (!keywords.includes(token)) keywords.push(token);
    if (keywords.length >= MAX_PROFILE_KEYWORDS) break;
  }
  return keywords;
}

/**
 * Relevance score and matched terms for one task.
 * Relevance only groups output — it never touches the attention score.
 */
export function profileRelevance(
  task: Record<string, unknown>,
  keywords: string[],
): { score: number; matched: string[] } {
  if (keywords.length === 0) return { score: 0, matched: [] };

  const fieldTokens = new Map<string, string[]>();
  for (const [field] of PROFILE_FIELDS) {
    fieldTokens.set(field, normTokens(task[field]));
  }

  let score = 0;
  const matched: string[] = [];

  for (const keyword of keywords) {
    let best = 0;
    for (const [field, weight] of PROFILE_FIELDS) {
      const tokens = fieldTokens.get(field) ?? [];
      if (tokens.some((token) => tokMatch(keyword, token))) {
        best = Math.max(best, weight);
      }
    }
    if (best > 0) {
      score += best;
      matched.push(keyword);
    }
  }

  return { score, matched };
}

/**
 * Split the attention queue using a focus profile.
 * Returns `null` when nothing matches, so the caller can fall back to
 * showing the plain engine signals.
 */
export function groupByProfile(
  attention: ScoredTask[],
  keywords: string[],
  maxItems = 5,
): { mine: ScoredTask[]; rest: ScoredTask[]; matches: Map<string, string[]> } | null {
  if (keywords.length === 0) return null;

  const scored = attention.map((task) => {
    const { score, matched } = profileRelevance(
      task as unknown as Record<string, unknown>,
      keywords,
    );
    return { task, score, matched };
  });

  const matchedRows = scored.filter((row) => row.score > 0);
  const restRows = scored.filter((row) => row.score === 0);
  if (matchedRows.length === 0) return null;

  const mine = matchedRows.slice(0, 3).map((row) => row.task);
  const rest = restRows
    .slice(0, Math.max(0, maxItems - mine.length))
    .map((row) => row.task);

  const matches = new Map<string, string[]>();
  for (const row of matchedRows) {
    matches.set(row.task.Task_ID, row.matched);
  }

  return { mine, rest, matches };
}
