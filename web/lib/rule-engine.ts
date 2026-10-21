/**
 * Executive Pulse — rule engine.
 *
 * Deterministic flag computation, attention scoring, ranking and the
 * selection helpers that back each module. Mirrors the Python reference
 * in `app/engine/rule_engine.py` — the parity suite asserts identical
 * output for a fixed fixture set.
 *
 * Design rules:
 *  - No randomness, no clock reads except the injected reference date.
 *  - Day-granularity date comparisons: a task due today is due today,
 *    never overdue.
 */

import type { Counts, ScoredTask, ScoreBand, Task } from "./types";

/** Weights that determine the attention score. */
export const SCORE_WEIGHTS = {
  decisionRequired: 5,
  criticalImpact: 5,
  highImpact: 3,
  blocked: 4,
  overdue: 4,
  atRisk: 2,
  stale: 2,
  dependencyRisk: 2,
} as const;

/** Inclusive days after a due date within which work counts as at risk. */
export const AT_RISK_WINDOW_DAYS = 2;

/** Hours without an update after which work counts as stale. */
export const STALE_AFTER_HOURS = 48;

/** Minimum attention score for an item to appear in the attention queue. */
export const ATTENTION_MIN_SCORE = 4;

export const SCORE_BANDS: Record<ScoreBand, { min: number; label: string }> = {
  Critical: { min: 10, label: "Critical" },
  High: { min: 7, label: "High" },
  Watch: { min: 4, label: "Watch" },
  Normal: { min: 0, label: "Normal" },
};

const BAND_ORDER: ScoreBand[] = ["Critical", "High", "Watch", "Normal"];

/** Resolve a score to its band. */
export function scoreBand(score: number): ScoreBand {
  for (const band of BAND_ORDER) {
    if (score >= SCORE_BANDS[band].min) return band;
  }
  return "Normal";
}

/**
 * Round half to even, matching Python's `round(x, 1)`.
 *
 * JS `Math.round` rounds half away from zero, so 0.25 -> 0.3 while
 * Python gives 0.2. The parity suite compares averages, so the rounding
 * mode has to match exactly.
 */
export function roundHalfEven(value: number, decimals = 1): number {
  const factor = 10 ** decimals;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;

  let rounded: number;
  if (diff > 0.5) rounded = floor + 1;
  else if (diff < 0.5) rounded = floor;
  else rounded = floor % 2 === 0 ? floor : floor + 1;

  return rounded / factor;
}

/**
 * Parse a reference date string into epoch milliseconds.
 *
 * The golden fixture stores a naive timestamp ("2026-09-28T10:30:00")
 * which JavaScript would otherwise read as local time — shifting the
 * whole engine by the machine's timezone offset. Naive timestamps are
 * treated as UTC so the reference and the task dates agree.
 */
export function parseReferenceDate(value: string): number {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return Date.now();
  if (/[Zz]$/.test(trimmed) || /[+-]\d{2}:?\d{2}$/.test(trimmed)) {
    return new Date(trimmed).getTime();
  }
  return Date.parse(`${trimmed.replace(" ", "T")}Z`);
}

/**
 * Parse a date-ish string into epoch milliseconds, or null.
 *
 * Dates are calendar dates ("2026-09-29"). Date-times keep their time
 * component ("2026-09-27 14:30", "2026-09-28 9:15"). Parsing is
 * deliberately UTC-anchored so results never depend on the machine's
 * timezone — the server's locale must not change what an executive sees.
 */
export function parseDate(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  if (!text) return null;

  // "YYYY-MM-DD" -> midnight UTC
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (dateOnly) {
    return Date.UTC(
      Number(dateOnly[1]),
      Number(dateOnly[2]) - 1,
      Number(dateOnly[3]),
    );
  }

  // "YYYY-MM-DD HH:mm(:ss)" or the ISO "T" form.
  // The hour may be one or two digits: spreadsheets commonly write
  // "2026-09-28 9:15".
  const dateTime =
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2}):(\d{2})(?::(\d{2}))?/.exec(text);
  if (dateTime) {
    return Date.UTC(
      Number(dateTime[1]),
      Number(dateTime[2]) - 1,
      Number(dateTime[3]),
      Number(dateTime[4]),
      Number(dateTime[5]),
      dateTime[6] ? Number(dateTime[6]) : 0,
    );
  }

  const fallback = Date.parse(text);
  return Number.isNaN(fallback) ? null : fallback;
}

/** Midnight (UTC) of the day containing the given timestamp. */
export function startOfDay(ms: number): number {
  const date = new Date(ms);
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

/** Whole days between two day-starts. */
export function daysBetween(fromMs: number, toMs: number): number {
  return Math.round((startOfDay(toMs) - startOfDay(fromMs)) / 86_400_000);
}

/** Split a dependency string into individual task ids. */
export function splitDependencies(dependency: string): string[] {
  return dependency
    .split(/[;,|]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

/**
 * Compute flags, reason codes and the attention score for one task.
 *
 * `allTasks` is used to resolve dependency risk.
 */
export function computeFlags(
  task: Task,
  allTasks: Task[],
  referenceMs: number,
): ScoredTask {
  const reasonCodes: string[] = [];
  let score = 0;

  const today = startOfDay(referenceMs);
  const dueMs = parseDate(task.Due_Date);
  const updatedMs = parseDate(task.Last_Updated);
  const isDone = task.Status === "Done";

  // OVERDUE: due before today
  let overdue = false;
  if (dueMs !== null) {
    if (startOfDay(dueMs) < today && !isDone) {
      overdue = true;
      reasonCodes.push("Overdue");
      score += SCORE_WEIGHTS.overdue;
    }
  }

  // AT_RISK: due today through today + AT_RISK_WINDOW_DAYS
  let atRisk = false;
  if (dueMs !== null) {
    const dueDay = startOfDay(dueMs);
    const horizon = today + AT_RISK_WINDOW_DAYS * 86_400_000;
    if (dueDay >= today && dueDay <= horizon && !isDone) {
      atRisk = true;
      reasonCodes.push("At risk (due within 48h)");
      score += SCORE_WEIGHTS.atRisk;
    }
  }

  // BLOCKED: status is Blocked, or a blocker is recorded
  let blocked = false;
  if (task.Status === "Blocked" || (task.Blocker && task.Blocker.trim() !== "")) {
    blocked = true;
    reasonCodes.push("Blocked");
    score += SCORE_WEIGHTS.blocked;
  }

  // STALE: no update for more than 48 hours
  let stale = false;
  if (updatedMs !== null && !isDone) {
    const hours = (referenceMs - updatedMs) / 3_600_000;
    if (hours > STALE_AFTER_HOURS) {
      stale = true;
      reasonCodes.push("Stale (>48h no update)");
      score += SCORE_WEIGHTS.stale;
    }
  }

  // DECISION_REQUIRED
  const decisionRequired = task.Executive_Decision_Required === true;
  if (decisionRequired) {
    reasonCodes.push("Executive decision required");
    score += SCORE_WEIGHTS.decisionRequired;
  }

  // HIGH_IMPACT
  let highImpact = false;
  if (task.Impact === "Critical") {
    highImpact = true;
    reasonCodes.push("Critical impact");
    score += SCORE_WEIGHTS.criticalImpact;
  } else if (task.Impact === "High") {
    highImpact = true;
    reasonCodes.push("High impact");
    score += SCORE_WEIGHTS.highImpact;
  }

  // DEPENDENCY_RISK: a dependency is blocked or overdue
  let dependencyRisk = false;
  const depIds = splitDependencies(task.Dependency ?? "");
  if (depIds.length > 0) {
    const risky: string[] = [];
    for (const depId of depIds) {
      const dep = allTasks.find((candidate) => candidate.Task_ID === depId);
      if (!dep) continue;
      const depDue = parseDate(dep.Due_Date);
      const depOverdue =
        depDue !== null && startOfDay(depDue) < today && dep.Status !== "Done";
      if (dep.Status === "Blocked" || depOverdue) {
        risky.push(depId);
      }
    }
    if (risky.length > 0) {
      dependencyRisk = true;
      reasonCodes.push(`Dependency risk (${risky.join(", ")})`);
      score += SCORE_WEIGHTS.dependencyRisk;
    }
  }

  return {
    ...task,
    overdue,
    at_risk: atRisk,
    blocked,
    stale,
    decision_required: decisionRequired,
    dependency_risk: dependencyRisk,
    high_impact: highImpact,
    reason_codes: reasonCodes,
    attention_score: score,
    score_band: scoreBand(score),
  };
}

/** Compute flags for every task. */
export function computeAllFlags(tasks: Task[], referenceMs: number): ScoredTask[] {
  return tasks.map((task) => computeFlags(task, tasks, referenceMs));
}

/**
 * Rank by attention score (desc) then due date (asc).
 * Tasks without a due date sort last.
 */
export function rankAttention(tasks: ScoredTask[]): ScoredTask[] {
  return [...tasks].sort((a, b) => {
    if (b.attention_score !== a.attention_score) {
      return b.attention_score - a.attention_score;
    }
    const aDue = parseDate(a.Due_Date);
    const bDue = parseDate(b.Due_Date);
    if (aDue === null && bDue === null) return 0;
    if (aDue === null) return 1;
    if (bDue === null) return -1;
    return aDue - bDue;
  });
}

/** Top N items above the attention threshold. */
export function getAttentionQueue(
  tasks: ScoredTask[],
  topN = 7,
  minScore = ATTENTION_MIN_SCORE,
): ScoredTask[] {
  return rankAttention(tasks.filter((task) => task.attention_score >= minScore)).slice(
    0,
    topN,
  );
}

/** Count every item above the attention threshold (not capped). */
export function countAttention(
  tasks: ScoredTask[],
  minScore = ATTENTION_MIN_SCORE,
): number {
  return tasks.filter((task) => task.attention_score >= minScore).length;
}

/** Items requiring an executive decision. */
export function getDecisionQueue(tasks: ScoredTask[]): ScoredTask[] {
  return rankAttention(tasks.filter((task) => task.decision_required));
}

/**
 * At-risk items: approaching a deadline, or high-impact open work.
 * Single source of truth for the At Risk view.
 */
export function getAtRisk(tasks: ScoredTask[]): ScoredTask[] {
  return rankAttention(
    tasks.filter(
      (task) => task.at_risk || (task.high_impact && task.Status !== "Done"),
    ),
  );
}

/** Blocked items, grouped for the friction view. */
export function getBlockedItems(tasks: ScoredTask[]): ScoredTask[] {
  return tasks
    .filter((task) => task.blocked)
    .slice()
    .sort((a, b) => {
      if (a.Department !== b.Department) return a.Department < b.Department ? -1 : 1;
      if (a.Blocker_Owner !== b.Blocker_Owner) {
        return a.Blocker_Owner < b.Blocker_Owner ? -1 : 1;
      }
      return b.attention_score - a.attention_score;
    });
}

/** Stale work. */
export function getStaleWork(tasks: ScoredTask[]): ScoredTask[] {
  return tasks
    .filter((task) => task.stale)
    .slice()
    .sort((a, b) => {
      if (b.attention_score !== a.attention_score) {
        return b.attention_score - a.attention_score;
      }
      const aUpdated = parseDate(a.Last_Updated) ?? Infinity;
      const bUpdated = parseDate(b.Last_Updated) ?? Infinity;
      return aUpdated - bUpdated;
    });
}

/**
 * Executive attention queue: Critical and High bands only.
 */
export function getExecutiveAttentionQueue(
  tasks: ScoredTask[],
  maxItems = 7,
  minBand: ScoreBand = "High",
): ScoredTask[] {
  const minScore = SCORE_BANDS[minBand].min;
  const filtered = tasks.filter(
    (task) => task.attention_score >= minScore && task.Status !== "Done",
  );
  return rankAttention(filtered).slice(0, maxItems);
}

/** Headline counts. */
export function getCounts(tasks: ScoredTask[]): Counts {
  return {
    total: tasks.length,
    open: tasks.filter((task) => task.Status !== "Done").length,
    attention: countAttention(tasks),
    decisions: getDecisionQueue(tasks).length,
    blocked: tasks.filter((task) => task.blocked).length,
    atRisk: getAtRisk(tasks).length,
    stale: tasks.filter((task) => task.stale).length,
    overdue: tasks.filter((task) => task.overdue).length,
    critical: tasks.filter((task) => task.score_band === "Critical").length,
  };
}

/**
 * Compute the delta between two dataset snapshots.
 */
export function computeChanges(
  current: ScoredTask[],
  previous: ScoredTask[] | null,
): {
  new_overdue: ScoredTask[];
  newly_blocked: ScoredTask[];
  resolved: ScoredTask[];
  status_changes: Array<{
    Task_ID: string;
    Task: string;
    Old_Status: string;
    New_Status: string;
    Owner: string;
  }>;
  new_decisions: ScoredTask[];
} {
  const empty = {
    new_overdue: [] as ScoredTask[],
    newly_blocked: [] as ScoredTask[],
    resolved: [] as ScoredTask[],
    status_changes: [] as Array<{
      Task_ID: string;
      Task: string;
      Old_Status: string;
      New_Status: string;
      Owner: string;
    }>,
    new_decisions: [] as ScoredTask[],
  };

  if (!previous || previous.length === 0) return empty;

  const previousById = new Map(previous.map((task) => [task.Task_ID, task]));

  for (const task of current) {
    const before = previousById.get(task.Task_ID);
    if (!before) continue;

    if (task.Status !== before.Status) {
      empty.status_changes.push({
        Task_ID: task.Task_ID,
        Task: task.Task,
        Old_Status: before.Status,
        New_Status: task.Status,
        Owner: task.Owner,
      });
    }

    if (task.overdue && !before.overdue) empty.new_overdue.push(task);
    if (task.blocked && !before.blocked) empty.newly_blocked.push(task);
    if (task.Status === "Done" && before.Status !== "Done") {
      empty.resolved.push(task);
    }
    if (task.decision_required && !before.decision_required) {
      empty.new_decisions.push(task);
    }
  }

  return empty;
}
