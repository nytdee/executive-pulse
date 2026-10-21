"""
Emit golden fixtures for the TypeScript engine parity suite.

The TypeScript port must behave identically to this Python reference.
This script runs a comprehensive, fixed dataset through the Python engine
and writes the expected outputs to `web/tests/fixtures/engine-golden.json`.

A fixed reference date is used so the fixtures never drift with the clock.

    python scripts/generate_golden_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.engine.intelligence import (  # noqa: E402
    analyze_owner_load,
    detect_cross_team_friction,
    detect_systemic_risks,
    generate_meeting_brief,
    get_blocked_friction_detailed,
    get_decision_queue_detailed,
    get_executive_attention_queue,
    get_org_pulse_enhanced,
)
from app.engine.rule_engine import (  # noqa: E402
    compute_all_flags,
    count_attention,
    get_at_risk,
    get_decision_queue,
    rank_attention,
)

OUTPUT = os.path.join(REPO_ROOT, "web", "tests", "fixtures", "engine-golden.json")

# Fixed reference date. 2026-09-28 is a Monday.
REFERENCE = datetime(2026, 9, 28, 10, 30, 0)

HEADER = [
    "Task_ID", "Task", "Project", "Department", "Owner", "Owner_Role", "Status",
    "Priority", "Start_Date", "Due_Date", "Completed_Date", "Impact", "Impact_Value",
    "Blocker", "Dependency", "Blocker_Owner", "Last_Updated",
    "Executive_Decision_Required", "Decision_By", "Decision_Requested",
    "Source_URL", "Notes",
]


def build_rows() -> list:
    d = lambda n: (REFERENCE + timedelta(days=n)).strftime("%Y-%m-%d")
    ts = lambda days, hour: (REFERENCE + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M")

    return [
        # 1 — maximum score: decision + critical impact + blocked + overdue
        ["T-001", "Critical blocked decision", "Alpha", "Strategy", "A One", "VP",
         "Blocked", "Critical", d(-20), d(-3), "", "Critical", 5000000,
         "Legal review pending", "", "Priya Legal", ts(-4, 9), "Yes", d(-1),
         "Approve escalation", "https://example.com/1", "Worst case"],

        # 2 — overdue only
        ["T-002", "Overdue item", "Alpha", "Sales", "B Two", "AE",
         "In Progress", "High", d(-15), d(-1), "", "High", 1000000,
         "", "", "", ts(-1, 9), "No", "", "", "", "Overdue only"],

        # 3 — due today (must NOT be overdue)
        ["T-003", "Due today", "Beta", "Marketing", "C Three", "CMO",
         "In Progress", "High", d(-10), d(0), "", "High", 2000000,
         "", "", "", ts(0, 8), "No", "", "", "", "Due today, not overdue"],

        # 4 — due tomorrow (at risk)
        ["T-004", "Due tomorrow", "Beta", "Marketing", "D Four", "Director",
         "In Progress", "Medium", d(-10), d(1), "", "Medium", 500000,
         "", "", "", ts(0, 9), "No", "", "", "", "At risk"],

        # 5 — due in two days (at risk, boundary)
        ["T-005", "Due in two days", "Beta", "Product", "E Five", "PM",
         "In Progress", "Medium", d(-10), d(2), "", "Medium", 400000,
         "", "", "", ts(0, 9), "No", "", "", "", "At risk boundary"],

        # 6 — due in three days (not at risk)
        ["T-006", "Due in three days", "Gamma", "Product", "F Six", "PM",
         "In Progress", "Low", d(-10), d(3), "", "Low", 100000,
         "", "", "", ts(0, 9), "No", "", "", "", "Not at risk"],

        # 7 — blocked via blocker column only
        ["T-007", "Blocked by column", "Gamma", "Operations", "G Seven", "PM",
         "In Progress", "Medium", d(-10), d(6), "", "Medium", 300000,
         "Vendor approval", "", "Ops Lead", ts(0, 9), "No", "", "", "", "Blocked by column"],

        # 8 — stale exactly 48h (NOT stale)
        ["T-008", "Stale boundary exact", "Gamma", "People", "H Eight", "Lead",
         "In Progress", "Low", d(-10), d(6), "", "Low", 0,
         "", "", "", (REFERENCE - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M"),
         "No", "", "", "", "Exactly 48h"],

        # 9 — stale 49h (stale)
        ["T-009", "Stale just over", "Gamma", "People", "I Nine", "Lead",
         "In Progress", "Low", d(-10), d(6), "", "Low", 0,
         "", "", "", (REFERENCE - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M"),
         "No", "", "", "", "49h stale"],

        # 10 — done, everything would otherwise flag
        ["T-010", "Completed work", "Delta", "Finance", "J Ten", "Director",
         "Done", "Critical", d(-30), d(-5), d(-6), "Critical", 9000000,
         "", "", "", ts(-6, 9), "No", "", "", "", "Done"],

        # 11 — dependency on a blocked task
        ["T-011", "Depends on blocked", "Delta", "Sales", "K Eleven", "AE",
         "In Progress", "High", d(-10), d(4), "", "High", 800000,
         "", "T-001", "", ts(0, 9), "No", "", "", "", "Dependency risk"],

        # 12 — dependency on an overdue task
        ["T-012", "Depends on overdue", "Delta", "Sales", "L Twelve", "AE",
         "In Progress", "High", d(-10), d(4), "", "High", 700000,
         "", "T-002", "", ts(0, 9), "No", "", "", "", "Dependency risk"],

        # 13 — multiple dependencies, one risky
        ["T-013", "Multiple dependencies", "Delta", "Tech", "M Thirteen", "Lead",
         "In Progress", "High", d(-10), d(4), "", "High", 600000,
         "", "T-001;T-006", "", ts(0, 9), "No", "", "", "", "Multi dependency"],

        # 14 — dependency chain: 14 -> 15 -> 16
        ["T-014", "Chain head", "Epsilon", "Tech", "N Fourteen", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 500000,
         "", "T-015", "", ts(0, 9), "No", "", "", "", "Chain"],

        ["T-015", "Chain middle", "Epsilon", "Tech", "O Fifteen", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 400000,
         "", "T-016", "", ts(0, 9), "No", "", "", "", "Chain"],

        ["T-016", "Chain tail", "Epsilon", "Tech", "P Sixteen", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 300000,
         "", "", "", ts(0, 9), "No", "", "", "", "Chain"],

        # 17 — recurring blocker (same blocker 3x)
        ["T-017", "Recurring blocker one", "Zeta", "Legal", "Q Seventeen", "GC",
         "Blocked", "High", d(-10), d(5), "", "High", 200000,
         "Contract pending", "", "Legal", ts(0, 9), "No", "", "", "", "Recurring"],

        ["T-018", "Recurring blocker two", "Zeta", "Sales", "R Eighteen", "AE",
         "Blocked", "High", d(-10), d(5), "", "High", 200000,
         "Contract pending", "", "Legal", ts(0, 9), "No", "", "", "", "Recurring"],

        ["T-019", "Recurring blocker three", "Zeta", "Ops", "S Nineteen", "PM",
         "Blocked", "High", d(-10), d(5), "", "High", 200000,
         "Contract pending", "", "Legal", ts(0, 9), "No", "", "", "", "Recurring"],

        # 20 — overloaded owner (many open items)
        ["T-020", "Overloaded one", "Eta", "Ops", "T Twenty", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 100000,
         "", "", "", ts(0, 9), "No", "", "", "", "Overload"],

        ["T-021", "Overloaded two", "Eta", "Ops", "T Twenty", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 100000,
         "", "", "", ts(0, 9), "No", "", "", "", "Overload"],

        ["T-022", "Overloaded three", "Eta", "Ops", "T Twenty", "Lead",
         "In Progress", "Medium", d(-10), d(5), "", "Medium", 100000,
         "", "", "", ts(0, 9), "No", "", "", "", "Overload"],

        # 23 — decision required, healthy otherwise
        ["T-023", "Decision only", "Theta", "Legal", "U TwentyThree", "GC",
         "In Progress", "Medium", d(-10), d(8), "", "Medium", 150000,
         "", "", "", ts(0, 9), "Yes", d(5), "Approve policy update", "", "Decision only"],

        # 24 — on hold, healthy
        ["T-024", "On hold", "Theta", "Marketing", "V TwentyFour", "Manager",
         "On Hold", "Low", d(-10), d(9), "", "Low", 0,
         "", "", "", ts(0, 9), "No", "", "", "", "On hold"],

        # 25 — not started, healthy
        ["T-025", "Not started", "Theta", "Product", "W TwentyFive", "PM",
         "Not Started", "Medium", d(2), d(20), "", "Medium", 250000,
         "", "", "", ts(0, 9), "No", "", "", "", "Not started"],

        # 26 — overdue + critical + blocked (band 13)
        ["T-026", "Overdue critical blocked", "Iota", "Tech", "X TwentySix", "Lead",
         "Blocked", "Critical", d(-20), d(-2), "", "Critical", 3000000,
         "Vendor API", "", "Eng", ts(-3, 9), "No", "", "", "", "Score 13"],
    ]


def jsonable(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def frame_to_records(frame) -> list:
    if frame is None or len(frame) == 0:
        return []
    records = []
    for record in frame.to_dict("records"):
        records.append({k: jsonable(v) for k, v in record.items()})
    return records


def main() -> None:
    import pandas as pd

    rows = build_rows()
    df = pd.DataFrame(rows, columns=HEADER)

    # Normalise exactly as the loader does, then score against the fixed clock.
    from app.data.loader import normalize_data, validate_data

    errors = validate_data(df)
    if errors:
        raise SystemExit(f"Fixture data failed validation: {errors}")
    df = normalize_data(df)
    df = compute_all_flags(df, REFERENCE)
    df = rank_attention(df)

    def slim(frame, columns):
        if frame is None or len(frame) == 0:
            return []
        keep = [c for c in columns if c in frame.columns]
        return frame_to_records(frame[keep])

    task_fields = [
        "Task_ID", "Task", "Project", "Department", "Owner", "Owner_Role", "Status",
        "Priority", "Due_Date", "Impact", "Impact_Value", "Blocker", "Dependency",
        "Blocker_Owner", "Last_Updated", "Executive_Decision_Required",
        "overdue", "at_risk", "blocked", "stale", "decision_required",
        "dependency_risk", "high_impact", "reason_codes", "attention_score", "score_band",
    ]

    attention = get_executive_attention_queue(df, max_items=7, min_band="High")
    at_risk = get_at_risk(df)
    decisions = get_decision_queue(df)
    decisions_detailed = get_decision_queue_detailed(df, REFERENCE)
    org = get_org_pulse_enhanced(df)
    blocked_detail = get_blocked_friction_detailed(df, REFERENCE)
    friction = detect_cross_team_friction(df, REFERENCE)
    loads = analyze_owner_load(df)
    systemic = detect_systemic_risks(df)
    brief = generate_meeting_brief(
        df, meeting_name="Q3 Board Review", meeting_date=REFERENCE, reference_date=REFERENCE
    )

    payload = {
        "referenceDate": REFERENCE.isoformat(),
        "rows": frame_to_records(df[task_fields]),
        "attention": slim(attention, task_fields),
        "atRisk": slim(at_risk, task_fields),
        "decisions": slim(decisions, task_fields),
        "decisionDetails": slim(decisions_detailed, task_fields + ["decision_urgency", "impact_context"]),
        "orgPulse": frame_to_records(org),
        "counts": {
            "total": len(df),
            "open": int((df["Status"] != "Done").sum()),
            "attention": count_attention(df),
            "decisions": len(decisions),
            "blocked": int((df["blocked"] == True).sum()),
            "atRisk": len(at_risk),
            "stale": int((df["stale"] == True).sum()),
            "overdue": int((df["overdue"] == True).sum()),
            "critical": int((df["score_band"] == "Critical").sum()),
        },
        "friction": [
            {
                "blockerOwner": f.blocker_owner,
                "blockerDept": f.blocker_dept,
                "blockedCount": f.blocked_count,
                "totalImpact": f.total_impact_value,
                "maxDaysBlocked": f.max_days_blocked,
                "severity": f.severity,
                "blockedTaskIds": [t["task_id"] for t in f.blocked_tasks],
            }
            for f in friction
        ],
        "ownerLoads": [
            {
                "owner": l.owner,
                "department": l.department,
                "totalOpen": l.total_open,
                "overdue": l.overdue,
                "blocked": l.blocked,
                "highImpact": l.high_impact,
                "decisionsRequired": l.decisions_required,
                "avgAttentionScore": l.avg_attention_score,
                "loadLevel": l.load_level,
            }
            for l in loads
        ],
        "systemicRisks": [
            {
                "type": s.pattern_type,
                "description": s.description,
                "severity": s.severity,
                "recommendation": s.recommendation,
                "affectedCount": len(s.affected_items),
                "affectedItems": s.affected_items,
            }
            for s in systemic
        ],
        "blockedSummary": blocked_detail["summary"],
        "meetingBrief": {
            "summary": brief["summary"],
            "decisionCount": len(brief["decisions"]),
            "criticalRiskCount": len(brief["critical_risk"]),
            "frictionCount": len(brief["friction_points"]),
            "systemicRiskCount": len(brief["systemic_risks"]),
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    # newline="\n" keeps the output byte-identical on every platform.
    # Without it Python writes CRLF on Windows and LF on Linux, and the
    # "fixtures are reproducible" check fails depending on where it runs.
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"Wrote golden fixtures to {OUTPUT}")
    print(f"  reference date : {REFERENCE.isoformat()}")
    print(f"  rows           : {len(df)}")
    print(f"  counts         : {payload['counts']}")


if __name__ == "__main__":
    main()
