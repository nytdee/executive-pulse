/**
 * Executive Pulse — intelligence layer.
 *
 * Turns raw flags into executive-grade signals: cross-team friction,
 * owner workload, systemic risk patterns, department pulse and the
 * meeting brief. Mirrors `app/engine/intelligence.py`.
 */

import { parseDate, rankAttention, roundHalfEven, startOfDay } from "./rule-engine";
import type {
  FrictionPoint,
  MeetingBrief,
  OrgPulseRow,
  OwnerLoad,
  ScoredTask,
  SystemicRisk,
} from "./types";

/** Empty org pulse rows keep the schema stable for API consumers. */
export const ORG_PULSE_COLUMNS: Array<keyof OrgPulseRow> = [
  "Department",
  "Total",
  "Open",
  "Done",
  "Completion_Rate",
  "Avg_Days_to_Complete",
  "Overdue",
  "Overdue_Pct",
  "Blocked",
  "Blocked_Pct",
  "At_Risk",
  "High_Impact",
  "Stale",
  "Stale_Pct",
  "Decisions",
  "Avg_Attention_Score",
  "Risk_Score",
];

const round1 = roundHalfEven;

/**
 * Detect cross-team friction: one team's work blocking another.
 */
export function detectCrossTeamFriction(
  tasks: ScoredTask[],
  referenceMs: number,
): FrictionPoint[] {
  const blockedWithOwner = tasks.filter(
    (task) => task.blocked && (task.Blocker_Owner ?? "").trim() !== "",
  );
  if (blockedWithOwner.length === 0) return [];

  const today = startOfDay(referenceMs);
  const owners = Array.from(new Set(blockedWithOwner.map((task) => task.Blocker_Owner)));
  const points: FrictionPoint[] = [];

  for (const blockerOwner of owners) {
    const ownerBlocks = blockedWithOwner.filter(
      (task) => task.Blocker_Owner === blockerOwner,
    );
    const blockerTasks = tasks.filter(
      (task) => task.Owner === blockerOwner && task.Status !== "Done",
    );

    let totalImpact = 0;
    let maxDays = 0;
    const blockedTasks: FrictionPoint["blocked_tasks"] = [];

    for (const task of ownerBlocks) {
      const due = parseDate(task.Due_Date);
      const daysBlocked =
        due === null ? 0 : Math.max(0, Math.floor((today - due) / 86_400_000));

      if (task.Impact_Value && task.Impact_Value > 0) {
        totalImpact += task.Impact_Value;
      }
      maxDays = Math.max(maxDays, daysBlocked);

      blockedTasks.push({
        task_id: task.Task_ID,
        task: task.Task,
        dept: task.Department,
        owner: task.Owner,
        impact: task.Impact,
        days_blocked: daysBlocked,
        blocker: task.Blocker,
      });
    }

    if (blockedTasks.length === 0) continue;

    const criticalCount = blockedTasks.filter((b) => b.impact === "Critical").length;
    const highCount = blockedTasks.filter((b) => b.impact === "High").length;

    let severity: FrictionPoint["severity"];
    if (criticalCount > 0 || totalImpact > 1_000_000 || maxDays > 7) {
      severity = "Critical";
    } else if (highCount > 1 || totalImpact > 250_000 || maxDays > 3) {
      severity = "High";
    } else {
      severity = "Watch";
    }

    points.push({
      blocker_owner: blockerOwner,
      blocker_dept: blockerTasks.length > 0 ? blockerTasks[0].Department : "",
      blocked_count: blockedTasks.length,
      total_impact_value: totalImpact,
      max_days_blocked: maxDays,
      severity,
      blocked_tasks: blockedTasks,
    });
  }

  const severityRank: Record<FrictionPoint["severity"], number> = {
    Critical: 0,
    High: 1,
    Watch: 2,
  };
  return points.sort(
    (a, b) =>
      severityRank[a.severity] - severityRank[b.severity] ||
      b.total_impact_value - a.total_impact_value,
  );
}

/** Analyse workload per owner to detect overload. */
export function analyzeOwnerLoad(tasks: ScoredTask[]): OwnerLoad[] {
  const owners = Array.from(new Set(tasks.map((task) => task.Owner)));
  const loads: OwnerLoad[] = [];

  for (const owner of owners) {
    const ownerTasks = tasks.filter((task) => task.Owner === owner);
    const openWork = ownerTasks.filter((task) => task.Status !== "Done");
    if (openWork.length === 0) continue;

    const overdue = openWork.filter((task) => task.overdue).length;
    const blocked = openWork.filter((task) => task.blocked).length;
    const highImpact = openWork.filter((task) => task.high_impact).length;
    const decisions = openWork.filter((task) => task.decision_required).length;
    const avgScore = round1(
      openWork.reduce((sum, task) => sum + task.attention_score, 0) / openWork.length,
    );

    const totalOpen = openWork.length;
    let loadLevel: OwnerLoad["load_level"];
    if (
      totalOpen > 8 ||
      overdue > 2 ||
      (blocked > 2 && highImpact > 1)
    ) {
      loadLevel = "Overloaded";
    } else if (totalOpen > 5 || overdue > 0 || blocked > 1) {
      loadLevel = "High";
    } else if (totalOpen > 2) {
      loadLevel = "Normal";
    } else {
      loadLevel = "Light";
    }

    loads.push({
      owner,
      department: ownerTasks.length > 0 ? ownerTasks[0].Department : "",
      total_open: totalOpen,
      overdue,
      blocked,
      high_impact: highImpact,
      decisions_required: decisions,
      avg_attention_score: avgScore,
      load_level: loadLevel,
    });
  }

  const levelRank: Record<OwnerLoad["load_level"], number> = {
    Overloaded: 0,
    High: 1,
    Normal: 2,
    Light: 3,
  };
  return loads.sort(
    (a, b) =>
      levelRank[a.load_level] - levelRank[b.load_level] ||
      b.avg_attention_score - a.avg_attention_score,
  );
}

/**
 * Find dependency chains: A depends on B depends on C.
 * Chains of 3+ items are single points of failure.
 */
export function findDependencyChains(tasks: ScoredTask[]): string[][] {
  const graph = new Map<string, string[]>();
  for (const task of tasks) {
    const raw = (task.Dependency ?? "").trim();
    if (!raw) continue;
    for (const depId of raw.split(/[;,|]/).map((p) => p.trim()).filter(Boolean)) {
      const dependents = graph.get(depId) ?? [];
      dependents.push(task.Task_ID);
      graph.set(depId, dependents);
    }
  }

  const chains: string[][] = [];
  const seen = new Set<string>();

  const walk = (node: string, path: string[], visiting: Set<string>): void => {
    if (visiting.has(node)) return;
    const current = [...path, node];
    const next = graph.get(node) ?? [];
    if (next.length === 0) {
      if (current.length >= 3) {
        const key = current.join("|");
        if (!seen.has(key)) {
          seen.add(key);
          chains.push(current);
        }
      }
      return;
    }
    for (const nxt of next) {
      walk(nxt, current, new Set([...visiting, node]));
    }
  };

  for (const node of graph.keys()) walk(node, [], new Set());
  return chains;
}

/** Detect systemic patterns across the portfolio. */
export function detectSystemicRisks(tasks: ScoredTask[]): SystemicRisk[] {
  const risks: SystemicRisk[] = [];

  // 1. Recurring blocker
  const blockerCounts = new Map<string, string[]>();
  for (const task of tasks) {
    if (!task.blocked) continue;
    const blocker = (task.Blocker ?? "").trim();
    if (!blocker) continue;
    blockerCounts.set(blocker, [...(blockerCounts.get(blocker) ?? []), task.Task_ID]);
  }
  for (const [blocker, affected] of blockerCounts) {
    if (affected.length >= 3) {
      risks.push({
        pattern_type: "recurring_blocker",
        description: `Blocker '${blocker}' affects ${affected.length} items`,
        affected_items: affected,
        severity: affected.length >= 5 ? "High" : "Watch",
        recommendation: `Address root cause of '${blocker}' - consider process change or dedicated owner`,
      });
    }
  }

  // 2. Owner overload
  for (const load of analyzeOwnerLoad(tasks)) {
    if (load.load_level !== "Overloaded") continue;
    const affected = tasks
      .filter((task) => task.Owner === load.owner && task.Status !== "Done")
      .map((task) => task.Task_ID);
    risks.push({
      pattern_type: "owner_overload",
      description: `${load.owner} has ${load.total_open} open items (${load.overdue} overdue, ${load.blocked} blocked)`,
      affected_items: affected,
      severity: load.overdue > 3 ? "Critical" : "High",
      recommendation: `Redistribute work from ${load.owner} or add capacity`,
    });
  }

  // 3. Department risk concentration
  const highImpact = tasks.filter((task) => task.high_impact);
  const totalHigh = highImpact.length;
  if (totalHigh > 0) {
    const byDept = new Map<string, string[]>();
    for (const task of highImpact) {
      byDept.set(task.Department, [
        ...(byDept.get(task.Department) ?? []),
        task.Task_ID,
      ]);
    }
    for (const [dept, affected] of byDept) {
      if (affected.length / totalHigh > 0.4) {
        risks.push({
          pattern_type: "dept_concentration",
          description: `${dept} holds ${affected.length}/${totalHigh} high-impact items (${Math.round((affected.length / totalHigh) * 100)}%)`,
          affected_items: affected,
          severity: "High",
          recommendation: `Review ${dept} capacity and risk distribution`,
        });
      }
    }
  }

  // 4. Stale cluster
  const staleByDept = new Map<string, string[]>();
  for (const task of tasks) {
    if (!task.stale) continue;
    staleByDept.set(task.Department, [
      ...(staleByDept.get(task.Department) ?? []),
      task.Task_ID,
    ]);
  }
  for (const [dept, affected] of staleByDept) {
    if (affected.length >= 3) {
      risks.push({
        pattern_type: "stale_cluster",
        description: `${dept} has ${affected.length} stale items (>48h no update)`,
        affected_items: affected,
        severity: "Watch",
        recommendation: `Request status updates from ${dept} owners`,
      });
    }
  }

  // 5. Dependency chains
  for (const chain of findDependencyChains(tasks)) {
    if (chain.length >= 3) {
      risks.push({
        pattern_type: "dependency_chain",
        description: `Dependency chain of ${chain.length} items: ${chain.join(" → ")}`,
        affected_items: chain,
        severity: "High",
        recommendation:
          "Review chain for single points of failure; consider parallelizing",
      });
    }
  }

  return risks;
}

/** Department-level rollup with a discriminating risk score. */
export function getOrgPulseEnhanced(tasks: ScoredTask[]): OrgPulseRow[] {
  const departments = Array.from(new Set(tasks.map((task) => task.Department))).sort();
  const rows: OrgPulseRow[] = [];

  for (const dept of departments) {
    const deptTasks = tasks.filter((task) => task.Department === dept);
    const openWork = deptTasks.filter((task) => task.Status !== "Done");
    const doneWork = deptTasks.filter((task) => task.Status === "Done");

    const total = deptTasks.length;
    const open = openWork.length;
    if (open === 0) continue;

    const overdue = openWork.filter((task) => task.overdue).length;
    const blocked = openWork.filter((task) => task.blocked).length;
    const highImpact = openWork.filter((task) => task.high_impact).length;
    const stale = openWork.filter((task) => task.stale).length;
    const decisions = openWork.filter((task) => task.decision_required).length;
    const atRisk = openWork.filter(
      (task) => task.at_risk || task.high_impact,
    ).length;

    const overduePct = round1((overdue / open) * 100);
    const blockedPct = round1((blocked / open) * 100);
    const stalePct = round1((stale / open) * 100);
    const completionRate = total > 0 ? round1((doneWork.length / total) * 100) : 0;

    // Python renders these as floats, so the format always carries one
    // decimal ("0.0%", "66.7%"). Match it exactly.
    const pct = (value: number): string => `${value.toFixed(1)}%`;

    const withDates = doneWork.filter(
      (task) => task.Start_Date && task.Completed_Date,
    );
    let avgDaysToComplete = 0;
    if (withDates.length > 0) {
      const totalDays = withDates.reduce((sum, task) => {
        const start = parseDate(task.Start_Date);
        const end = parseDate(task.Completed_Date);
        if (start === null || end === null) return sum;
        return sum + Math.round((end - start) / 86_400_000);
      }, 0);
      avgDaysToComplete = round1(totalDays / withDates.length);
    }

    // Rate-based so the score discriminates between departments.
    const riskScore = round1(
      100 *
        ((overduePct / 100) * 0.3 +
          (blockedPct / 100) * 0.25 +
          (stalePct / 100) * 0.15 +
          (highImpact / open) * 0.2 +
          (decisions / open) * 0.1),
    );

    rows.push({
      Department: dept,
      Total: total,
      Open: open,
      Done: doneWork.length,
      Completion_Rate: pct(completionRate),
      Avg_Days_to_Complete: avgDaysToComplete,
      Overdue: overdue,
      Overdue_Pct: pct(overduePct),
      Blocked: blocked,
      Blocked_Pct: pct(blockedPct),
      At_Risk: atRisk,
      High_Impact: highImpact,
      Stale: stale,
      Stale_Pct: pct(stalePct),
      Decisions: decisions,
      Avg_Attention_Score: round1(
        openWork.reduce((sum, task) => sum + task.attention_score, 0) / open,
      ),
      Risk_Score: riskScore,
    });
  }

  return rows.sort((a, b) => b.Risk_Score - a.Risk_Score);
}

/** Decision queue with urgency and impact context. */
export function getDecisionQueueDetailed(
  tasks: ScoredTask[],
  referenceMs: number,
): ScoredTask[] {
  const today = startOfDay(referenceMs);
  const decisions = tasks.filter((task) => task.decision_required);

  return rankAttention(decisions).map((task) => {
    let urgency = "No deadline";
    if (task.overdue) {
      urgency = "URGENT - Overdue";
    } else {
      const due = parseDate(task.Due_Date);
      if (due !== null) {
        const days = Math.round((startOfDay(due) - today) / 86_400_000);
        if (days < 0) urgency = "URGENT - Overdue";
        else if (days === 0) urgency = "URGENT - Due today";
        else if (days <= 2) urgency = `Due in ${days} day(s)`;
        else if (days <= 7) urgency = `Due in ${days} days`;
      }
    }
    // Match the Python reference exactly: plain comma grouping, not the
    // Indian lakh/crore digit grouping.
    const money =
      task.Impact_Value > 0
        ? ` (₹${task.Impact_Value.toLocaleString("en-US")})`
        : "";
    return Object.assign(task, {
      decision_urgency: urgency,
      impact_context: `${task.Impact} impact${money}`,
    });
  });
}

/** Blocked work grouped by department and blocker owner. */
export function getBlockedFrictionDetailed(
  tasks: ScoredTask[],
  referenceMs: number,
) {
  const blocked = tasks.filter((task) => task.blocked);
  if (blocked.length === 0) {
    return {
      byDepartment: {} as Record<string, { count: number; items: ScoredTask[] }>,
      byBlockerOwner: {} as Record<
        string,
        { count: number; blocker_dept: string; items: ScoredTask[] }
      >,
      crossTeam: [] as FrictionPoint[],
      summary: {
        total_blocked: 0,
        departments_affected: 0,
        blocker_owners: 0,
        cross_team_friction_points: 0,
      },
    };
  }

  const byDepartment: Record<string, { count: number; items: ScoredTask[] }> = {};
  for (const dept of Array.from(new Set(blocked.map((t) => t.Department))).sort()) {
    const items = blocked
      .filter((task) => task.Department === dept)
      .sort((a, b) => b.attention_score - a.attention_score);
    byDepartment[dept] = { count: items.length, items };
  }

  const byBlockerOwner: Record<
    string,
    { count: number; blocker_dept: string; items: ScoredTask[] }
  > = {};
  for (const owner of Array.from(
    new Set(blocked.map((t) => (t.Blocker_Owner ?? "").trim()).filter(Boolean)),
  ).sort()) {
    const items = blocked
      .filter((task) => task.Blocker_Owner === owner)
      .sort((a, b) => b.attention_score - a.attention_score);
    byBlockerOwner[owner] = {
      count: items.length,
      blocker_dept: items.length > 0 ? items[0].Department : "",
      items,
    };
  }

  return {
    byDepartment,
    byBlockerOwner,
    crossTeam: detectCrossTeamFriction(tasks, referenceMs),
    summary: {
      total_blocked: blocked.length,
      departments_affected: Object.keys(byDepartment).length,
      blocker_owners: Object.keys(byBlockerOwner).length,
      cross_team_friction_points: detectCrossTeamFriction(tasks, referenceMs).length,
    },
  };
}

/** Build an agenda-ready meeting brief. */
export function generateMeetingBrief(
  tasks: ScoredTask[],
  options: {
    meetingName?: string;
    referenceMs: number;
    focusDepartments?: string[] | null;
    focusOwners?: string[] | null;
  },
): MeetingBrief {
  const { meetingName = "", referenceMs, focusDepartments, focusOwners } = options;

  let brief = tasks;
  if (focusDepartments && focusDepartments.length > 0) {
    brief = brief.filter((task) => focusDepartments.includes(task.Department));
  }
  if (focusOwners && focusOwners.length > 0) {
    brief = brief.filter((task) => focusOwners.includes(task.Owner));
  }
  brief = brief.filter((task) => task.Status !== "Done");

  const decisions = rankAttention(brief.filter((task) => task.decision_required));
  const criticalRisk = rankAttention(
    brief.filter((task) => task.attention_score >= 10),
  );
  const highRisk = rankAttention(
    brief.filter(
      (task) => task.attention_score >= 7 && task.attention_score < 10,
    ),
  );
  const blocked = rankAttention(brief.filter((task) => task.blocked));
  const overdue = rankAttention(brief.filter((task) => task.overdue));

  const friction = detectCrossTeamFriction(brief, referenceMs);
  const systemic = detectSystemicRisks(brief);
  const overloadedOwners = analyzeOwnerLoad(brief).filter((load) =>
    ["Overloaded", "High"].includes(load.load_level),
  );

  const dateFormat = new Date(referenceMs)
    .toISOString()
    .replace("T", " ")
    .slice(0, 16);

  return {
    meeting_name: meetingName,
    meeting_date: dateFormat,
    generated_at: new Date(referenceMs).toISOString().slice(0, 16).replace("T", " "),
    summary: {
      total_open: brief.length,
      decisions_required: decisions.length,
      critical_risk: criticalRisk.length,
      high_risk: highRisk.length,
      blocked: blocked.length,
      overdue: overdue.length,
      friction_points: friction.length,
      systemic_risks: systemic.length,
      overloaded_owners: overloadedOwners.length,
    },
    decisions,
    critical_risk: criticalRisk,
    high_risk: highRisk,
    blocked,
    overdue,
    friction_points: friction,
    systemic_risks: systemic,
    owner_loads: overloadedOwners,
  };
}
