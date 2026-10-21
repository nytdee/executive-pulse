"use client";

/**
 * Executive Pulse — signal row and detail drawer.
 *
 * The default view of an item is four lines: what it is, who owns it,
 * why it matters, and why it surfaced. Everything else opens on demand.
 */

import { useState } from "react";

import {
  bandTone,
  formatDateFull,
  formatDateTime,
  formatMoney,
  impactLine,
  scoreBreakdown,
  signalLine,
} from "@/lib/format";
import type { ScoredTask } from "@/lib/types";

/** A compact row: the default representation of an attention item. */
export function SignalRow({
  task,
  referenceMs,
  matchTerms,
  action,
}: {
  task: ScoredTask;
  referenceMs: number;
  matchTerms?: string[];
  action?: React.ReactNode;
}) {
  const signal = signalLine(task, referenceMs);
  const tone = bandTone(task.score_band);
  const impact = impactLine(task);
  const meta = [task.Department, task.Owner].filter(Boolean).join(" · ");

  return (
    <div className="sig">
      <span className="sig-bar" data-tone={tone} aria-hidden="true" />
      <div className="sig-main">
        <div className="sig-title">{task.Task}</div>
        {meta ? <div className="sig-meta">{meta}</div> : null}
        {impact ? <div className="sig-impact">{impact}</div> : null}
        <div className="sig-signal">
          <strong>{signal.text}</strong>
        </div>
        {matchTerms?.length ? (
          <div className="sig-matches">Matches: {matchTerms.slice(0, 4).join(", ")}</div>
        ) : null}
      </div>
      {action ? <div className="sig-side">{action}</div> : null}
    </div>
  );
}

/** Full context for one item, behind a disclosure. */
export function DetailBody({
  task,
  referenceMs,
}: {
  task: ScoredTask;
  referenceMs: number;
}) {
  const parts = scoreBreakdown(task);
  const reasons = task.reason_codes ?? [];

  return (
    <div>
      <h3 style={{ fontSize: "1.0625rem", fontWeight: 600, margin: 0 }}>
        {task.Task}
      </h3>
      <div className="dw-muted" style={{ marginTop: "0.2rem" }}>
        {[task.Department, task.Project].filter(Boolean).join(" · ")}
      </div>

      <div className="dw-kicker">Why this matters</div>
      {reasons.length > 0 ? (
        reasons.map((reason) => (
          <div className="dw-body" key={reason}>
            — {reason}
          </div>
        ))
      ) : (
        <div className="dw-muted">No active risk flags.</div>
      )}

      {parts.length > 0 ? (
        <>
          <div className="dw-kicker">Attention score</div>
          {parts.map((part) => (
            <div className="dw-score-row" key={part.label}>
              <span>{part.label}</span>
              <span>{part.points}</span>
            </div>
          ))}
          <div className="dw-total">
            <span>Total</span>
            <span>{task.attention_score}</span>
          </div>
        </>
      ) : null}

      {task.decision_required ? (
        <>
          <div className="dw-kicker">Decision required</div>
          <div className="dw-body">
            {task.Decision_Requested || "Executive input requested."}
          </div>
          {task.Decision_By ? (
            <div className="dw-muted">Decide by {formatDateFull(task.Decision_By)}</div>
          ) : null}
        </>
      ) : null}

      {task.Blocker || task.Blocker_Owner || task.Dependency ? (
        <>
          <div className="dw-kicker">What is blocking it</div>
          {task.Blocker ? <div className="dw-body">{task.Blocker}</div> : null}
          {task.Blocker_Owner ? (
            <div className="dw-muted">Blocker owner: {task.Blocker_Owner}</div>
          ) : null}
          {task.Dependency ? (
            <div className="dw-muted">Depends on: {task.Dependency}</div>
          ) : null}
        </>
      ) : null}

      <div className="dw-kicker">Impact</div>
      <div className="dw-body">
        {[task.Impact, formatMoney(task.Impact_Value)].filter(Boolean).join(" · ")}
      </div>

      <div className="dw-kicker">Ownership and timing</div>
      <div className="dw-body">
        {[task.Owner, task.Owner_Role].filter(Boolean).join(" · ")}
      </div>
      <div className="dw-muted">
        {[
          task.Due_Date ? `Due ${formatDateFull(task.Due_Date)}` : "",
          `Status ${task.Status}`,
          `Priority ${task.Priority}`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </div>
      {task.Last_Updated ? (
        <div className="dw-muted">
          Last updated {formatDateTime(task.Last_Updated)}
        </div>
      ) : null}

      {task.Notes ? (
        <>
          <div className="dw-kicker">Notes</div>
          <div className="dw-body">{task.Notes}</div>
        </>
      ) : null}

      {task.Source_URL ? (
        <p style={{ marginTop: "1rem" }}>
          <a href={task.Source_URL} target="_blank" rel="noreferrer">
            View source
          </a>
        </p>
      ) : null}
    </div>
  );
}

/** A row with its detail behind a disclosure. */
export function SignalRowWithDetail({
  task,
  referenceMs,
  matchTerms,
}: {
  task: ScoredTask;
  referenceMs: number;
  matchTerms?: string[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <SignalRow
        task={task}
        referenceMs={referenceMs}
        matchTerms={matchTerms}
        action={
          <button
            type="button"
            className="ep-button"
            data-variant="quiet"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? "Close" : "Review"}
          </button>
        }
      />
      {open ? (
        <div
          style={{
            padding: "0.9rem 1rem 0.9rem 1rem",
            borderBottom: "1px solid var(--color-line-soft)",
            background: "var(--color-surface)",
          }}
        >
          <DetailBody task={task} referenceMs={referenceMs} />
        </div>
      ) : null}
    </div>
  );
}
