/**
 * Executive Pulse — formatting helpers.
 *
 * Mirrors the Python presentation layer (`app/components/ui.py`) so the
 * web app renders exactly what the Streamlit app renders.
 */

import { parseDate, startOfDay } from "@/lib/rule-engine";
import type { ScoredTask } from "@/lib/types";

/** Format an amount in Indian currency notation (lakh / crore). */
export function formatMoney(value: unknown): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0) return "";
  if (amount >= 10_000_000) {
    return `₹${trimZeros(amount / 10_000_000, 2)}Cr`;
  }
  if (amount >= 100_000) {
    return `₹${trimZeros(amount / 100_000, 1)}L`;
  }
  if (amount >= 1_000) {
    return `₹${Math.round(amount / 1_000)}K`;
  }
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

function trimZeros(value: number, decimals: number): string {
  return value
    .toFixed(decimals)
    .replace(/\.?0+$/, "");
}

/** Format a date as "Sep 29" (or "29 Sep" style fallback). */
export function formatDate(value: unknown): string {
  const ms = parseDate(value as string);
  if (ms === null) return "";
  const date = new Date(ms);
  const month = date.toLocaleString("en-US", {
    month: "short",
    timeZone: "UTC",
  });
  return `${month} ${date.getUTCDate()}`;
}

/** Format a date with the year: "Sep 29, 2026". */
export function formatDateFull(value: unknown): string {
  const ms = parseDate(value as string);
  if (ms === null) return "";
  const date = new Date(ms);
  const month = date.toLocaleString("en-US", {
    month: "short",
    timeZone: "UTC",
  });
  return `${month} ${date.getUTCDate()}, ${date.getUTCFullYear()}`;
}

/** Format a date-time: "Sep 27, 2026 14:30". */
export function formatDateTime(value: unknown): string {
  const ms = parseDate(value as string);
  if (ms === null) return "";
  const date = new Date(ms);
  const month = date.toLocaleString("en-US", {
    month: "short",
    timeZone: "UTC",
  });
  const hours = String(date.getUTCHours()).padStart(2, "0");
  const minutes = String(date.getUTCMinutes()).padStart(2, "0");
  return `${month} ${date.getUTCDate()}, ${date.getUTCFullYear()} ${hours}:${minutes}`;
}

/** Human relative due text: "3d overdue", "Due today", "Due in 4d". */
export function dueText(dueDate: unknown, referenceMs: number): string {
  const ms = parseDate(dueDate as string);
  if (ms === null) return "";
  const days = Math.round(
    (startOfDay(ms) - startOfDay(referenceMs)) / 86_400_000,
  );
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `Due in ${days}d`;
}

/** Whole days since a timestamp. */
export function daysSince(value: unknown, referenceMs: number): number | null {
  const ms = parseDate(value as string);
  if (ms === null) return null;
  return Math.max(
    0,
    Math.round((startOfDay(referenceMs) - startOfDay(ms)) / 86_400_000),
  );
}

/** Impact description: "₹5Cr at risk" or "Critical impact". */
export function impactLine(task: ScoredTask): string {
  const money = formatMoney(task.Impact_Value);
  if (money) return `${money} at risk`;
  if (task.Impact) return `${task.Impact} impact`;
  return "";
}

export type SignalTone = "critical" | "warning" | "navy" | "muted";

/** The single most important reason this item surfaced. */
export function primarySignal(task: ScoredTask): { text: string; tone: SignalTone } {
  if (task.decision_required) return { text: "Decision required", tone: "navy" };
  if (task.overdue) return { text: "Overdue", tone: "critical" };
  if (task.blocked) {
    return task.Impact === "Critical"
      ? { text: "Critical blocker", tone: "critical" }
      : { text: "Blocked", tone: "warning" };
  }
  if (task.at_risk) return { text: "At risk", tone: "warning" };
  if (task.dependency_risk) {
    return { text: "Dependency at risk", tone: "warning" };
  }
  if (task.stale) return { text: "No recent update", tone: "muted" };
  if (task.high_impact) return { text: "High impact", tone: "muted" };
  return { text: "Watch", tone: "muted" };
}

/** Primary signal plus the due context. */
export function signalLine(
  task: ScoredTask,
  referenceMs: number,
): { text: string; tone: SignalTone } {
  const { text, tone } = primarySignal(task);
  const due = dueText(task.Due_Date, referenceMs);
  if (due && !text.includes(due)) return { text: `${text} · ${due}`, tone };
  return { text, tone };
}

/** Band to visual tone. */
export function bandTone(band: string): SignalTone {
  if (band === "Critical") return "critical";
  if (band === "High") return "warning";
  return "navy";
}

/** The scoring breakdown, mirroring the engine weights. */
export function scoreBreakdown(
  task: ScoredTask,
): Array<{ points: string; label: string }> {
  const parts: Array<{ points: string; label: string }> = [];
  if (task.decision_required) {
    parts.push({ points: "+5", label: "Executive decision required" });
  }
  if (task.Impact === "Critical") {
    parts.push({ points: "+5", label: "Critical impact" });
  } else if (task.Impact === "High") {
    parts.push({ points: "+3", label: "High impact" });
  }
  if (task.blocked) parts.push({ points: "+4", label: "Blocked" });
  if (task.overdue) parts.push({ points: "+4", label: "Overdue" });
  if (task.at_risk) parts.push({ points: "+2", label: "Due within 48 hours" });
  if (task.stale) parts.push({ points: "+2", label: "No update in 48+ hours" });
  if (task.dependency_risk) {
    const dependency = (task.Dependency ?? "").trim();
    parts.push({
      points: "+2",
      label: dependency
        ? `Dependency at risk (${dependency})`
        : "Dependency at risk",
    });
  }
  return parts;
}

/** Format the reference date for the header. */
export function formatReferenceDay(referenceMs: number): string {
  return new Date(referenceMs).toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Format a timestamp for the "last refreshed" line. */
export function formatRefreshed(referenceMs: number): string {
  return new Date(referenceMs).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}
