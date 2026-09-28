"""
Rule engine for Executive Pulse.
Computes flags, attention scores, and reason codes for each task.
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class FlagResult:
    """Result of flag computation for a single task."""
    overdue: bool
    at_risk: bool
    blocked: bool
    stale: bool
    decision_required: bool
    dependency_risk: bool
    high_impact: bool
    reason_codes: List[str]
    attention_score: int
    score_band: str


def compute_flags(row: pd.Series, all_tasks: pd.DataFrame, reference_date: datetime = None) -> FlagResult:
    """Compute all flags for a single task row."""
    if reference_date is None:
        reference_date = datetime.now()

    reason_codes = []
    score = 0

    # Extract values
    status = row.get("Status", "")
    due_date = row.get("Due_Date")
    last_updated = row.get("Last_Updated")
    impact = row.get("Impact", "")
    blocker = row.get("Blocker", "")
    dependency = row.get("Dependency", "")
    exec_decision = row.get("Executive_Decision_Required", False)

    # OVERDUE: due date < today AND status != Done
    overdue = False
    if pd.notna(due_date) and due_date < reference_date and status != "Done":
        overdue = True
        reason_codes.append("Overdue")
        score += 4

    # AT_RISK: due date <= today + 2 days AND status != Done
    at_risk = False
    if pd.notna(due_date) and due_date <= reference_date + timedelta(days=2) and status != "Done":
        if not overdue:  # Don't double-count if already overdue
            at_risk = True
            reason_codes.append("At risk (due within 48h)")
            score += 2

    # BLOCKED: status == Blocked OR Blocker is populated
    blocked = False
    if status == "Blocked" or (isinstance(blocker, str) and blocker.strip()):
        blocked = True
        reason_codes.append("Blocked")
        score += 4

    # STALE: last updated > 48h ago AND status != Done
    stale = False
    if pd.notna(last_updated) and (reference_date - last_updated) > timedelta(hours=48) and status != "Done":
        stale = True
        reason_codes.append("Stale (>48h no update)")
        score += 2

    # DECISION_REQUIRED: Executive_Decision_Required == Yes
    decision_required = False
    if exec_decision:
        decision_required = True
        reason_codes.append("Executive decision required")
        score += 5

    # HIGH_IMPACT: Impact in {High, Critical}
    high_impact = False
    if impact == "Critical":
        high_impact = True
        reason_codes.append("Critical impact")
        score += 5
    elif impact == "High":
        high_impact = True
        reason_codes.append("High impact")
        score += 3

    # DEPENDENCY_RISK: dependency exists and linked dependency is overdue/blocked
    dependency_risk = False
    if isinstance(dependency, str) and dependency.strip():
        dep_task = all_tasks[all_tasks["Task_ID"] == dependency.strip()]
        if not dep_task.empty:
            dep_row = dep_task.iloc[0]
            dep_status = dep_row.get("Status", "")
            dep_due = dep_row.get("Due_Date")
            if dep_status == "Blocked" or (pd.notna(dep_due) and dep_due < reference_date and dep_status != "Done"):
                dependency_risk = True
                reason_codes.append(f"Dependency risk ({dependency})")
                score += 2

    # Determine score band
    if score >= 10:
        score_band = "Critical"
    elif score >= 7:
        score_band = "High"
    elif score >= 4:
        score_band = "Watch"
    else:
        score_band = "Normal"

    return FlagResult(
        overdue=overdue,
        at_risk=at_risk,
        blocked=blocked,
        stale=stale,
        decision_required=decision_required,
        dependency_risk=dependency_risk,
        high_impact=high_impact,
        reason_codes=reason_codes,
        attention_score=score,
        score_band=score_band,
    )


def compute_all_flags(df: pd.DataFrame, reference_date: datetime = None) -> pd.DataFrame:
    """Compute flags for all tasks and return enriched dataframe."""
    if reference_date is None:
        reference_date = datetime.now()

    results = []
    for _, row in df.iterrows():
        flags = compute_flags(row, df, reference_date)
        results.append({
            "overdue": flags.overdue,
            "at_risk": flags.at_risk,
            "blocked": flags.blocked,
            "stale": flags.stale,
            "decision_required": flags.decision_required,
            "dependency_risk": flags.dependency_risk,
            "high_impact": flags.high_impact,
            "reason_codes": "; ".join(flags.reason_codes),
            "attention_score": flags.attention_score,
            "score_band": flags.score_band,
        })

    flags_df = pd.DataFrame(results, index=df.index)
    return pd.concat([df, flags_df], axis=1)


def rank_attention(df: pd.DataFrame) -> pd.DataFrame:
    """Sort tasks by attention score (desc) then due date (asc)."""
    return df.sort_values(
        by=["attention_score", "Due_Date"],
        ascending=[False, True],
        na_position="last"
    ).reset_index(drop=True)


def get_attention_queue(df: pd.DataFrame, top_n: int = 7, min_score: int = 4) -> pd.DataFrame:
    """Get top N attention items above minimum score."""
    filtered = df[df["attention_score"] >= min_score]
    return rank_attention(filtered).head(top_n)


def get_decision_queue(df: pd.DataFrame) -> pd.DataFrame:
    """Get items requiring executive decision."""
    return df[df["decision_required"] == True].sort_values(
        by=["attention_score", "Due_Date"],
        ascending=[False, True]
    ).reset_index(drop=True)


def get_at_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Get at-risk items (high impact + due soon or blocked)."""
    mask = (
        (df["at_risk"] == True) |
        ((df["high_impact"] == True) & (df["Status"] != "Done") & (df["attention_score"] >= 4))
    )
    return df[mask].sort_values(
        by=["attention_score", "Due_Date"],
        ascending=[False, True]
    ).reset_index(drop=True)


def get_blocked_items(df: pd.DataFrame) -> pd.DataFrame:
    """Get blocked items grouped by department and blocker owner."""
    blocked = df[df["blocked"] == True].copy()
    return blocked.sort_values(
        by=["Department", "Blocker_Owner", "attention_score"],
        ascending=[True, True, False]
    ).reset_index(drop=True)


def get_stale_work(df: pd.DataFrame) -> pd.DataFrame:
    """Get stale work items."""
    stale = df[df["stale"] == True].copy()
    return stale.sort_values(
        by=["attention_score", "Last_Updated"],
        ascending=[False, True]
    ).reset_index(drop=True)


def get_org_pulse(df: pd.DataFrame) -> pd.DataFrame:
    """Compute department-level rollup metrics."""
    metrics = []
    for dept in sorted(df["Department"].unique()):
        dept_df = df[df["Department"] == dept]
        open_work = dept_df[dept_df["Status"] != "Done"]
        overdue = open_work[open_work["overdue"] == True]
        blocked = open_work[open_work["blocked"] == True]
        high_impact = open_work[open_work["high_impact"] == True]

        metrics.append({
            "Department": dept,
            "Open": len(open_work),
            "Overdue": len(overdue),
            "Blocked": len(blocked),
            "High_Impact": len(high_impact),
            "Decision_Required": len(open_work[open_work["decision_required"] == True]),
            "Avg_Attention_Score": round(open_work["attention_score"].mean(), 1) if len(open_work) > 0 else 0,
        })

    return pd.DataFrame(metrics)


def compute_changes(current: pd.DataFrame, previous: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Compute delta between current and previous dataset snapshots."""
    changes = {
        "new_overdue": pd.DataFrame(),
        "newly_blocked": pd.DataFrame(),
        "resolved": pd.DataFrame(),
        "status_changes": pd.DataFrame(),
        "new_decisions": pd.DataFrame(),
    }

    if previous is None or previous.empty:
        return changes

    # Merge on Task_ID
    curr_ids = set(current["Task_ID"])
    prev_ids = set(previous["Task_ID"])

    # New items
    new_ids = curr_ids - prev_ids
    if new_ids:
        changes["new_items"] = current[current["Task_ID"].isin(new_ids)]

    # Removed items
    removed_ids = prev_ids - curr_ids
    if removed_ids:
        changes["removed_items"] = previous[previous["Task_ID"].isin(removed_ids)]

    # Compare existing items
    common_ids = curr_ids & prev_ids
    for task_id in common_ids:
        curr = current[current["Task_ID"] == task_id].iloc[0]
        prev = previous[previous["Task_ID"] == task_id].iloc[0]

        # Status changes
        if curr["Status"] != prev["Status"]:
            changes["status_changes"] = pd.concat([
                changes["status_changes"],
                pd.DataFrame([{
                    "Task_ID": task_id,
                    "Task": curr["Task"],
                    "Old_Status": prev["Status"],
                    "New_Status": curr["Status"],
                    "Owner": curr["Owner"],
                }])
            ], ignore_index=True)

        # New overdue
        if curr.get("overdue", False) and not prev.get("overdue", False):
            changes["new_overdue"] = pd.concat([
                changes["new_overdue"],
                pd.DataFrame([curr])
            ], ignore_index=True)

        # Newly blocked
        if curr.get("blocked", False) and not prev.get("blocked", False):
            changes["newly_blocked"] = pd.concat([
                changes["newly_blocked"],
                pd.DataFrame([curr])
            ], ignore_index=True)

        # Resolved (was overdue/blocked, now done)
        if curr["Status"] == "Done" and prev["Status"] != "Done":
            changes["resolved"] = pd.concat([
                changes["resolved"],
                pd.DataFrame([curr])
            ], ignore_index=True)

        # New decision required
        if curr.get("decision_required", False) and not prev.get("decision_required", False):
            changes["new_decisions"] = pd.concat([
                changes["new_decisions"],
                pd.DataFrame([curr])
            ], ignore_index=True)

    return changes