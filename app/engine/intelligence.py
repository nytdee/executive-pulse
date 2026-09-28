"""
Intelligence layer for Executive Pulse.
Transforms raw flags into executive-grade attention signals.
"""

from __future__ import annotations
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class FrictionPoint:
    """A cross-team friction point."""
    blocker_task_id: str
    blocker_task: str
    blocker_owner: str
    blocker_dept: str
    blocked_tasks: List[Dict[str, Any]]
    blocked_count: int
    total_impact_value: float
    max_days_blocked: int
    severity: str  # "Critical", "High", "Watch"


@dataclass
class OwnerLoad:
    """Workload analysis for an owner."""
    owner: str
    department: str
    total_open: int
    overdue: int
    blocked: int
    high_impact: int
    decisions_required: int
    avg_attention_score: float
    load_level: str  # "Overloaded", "High", "Normal", "Light"


@dataclass
class SystemicRisk:
    """Systemic pattern detected across the portfolio."""
    pattern_type: str  # "recurring_blocker", "owner_overload", "dept_concentration", "stale_cluster"
    description: str
    affected_items: List[str]
    severity: str
    recommendation: str


def detect_cross_team_friction(df: pd.DataFrame) -> List[FrictionPoint]:
    """Detect cross-team friction: where one team's work blocks another."""
    friction_points = []

    # Find all blockers with owners
    blocked_items = df[
        (df.get("blocked", False) == True) &
        (df["Blocker_Owner"].astype(str).str.strip() != "")
    ].copy()

    if blocked_items.empty:
        return friction_points

    # Group by blocker owner (the person/team causing the block)
    for blocker_owner in blocked_items["Blocker_Owner"].unique():
        if not blocker_owner or not str(blocker_owner).strip():
            continue

        owner_blocks = blocked_items[blocked_items["Blocker_Owner"] == blocker_owner]

        # Get the blocker task(s) this owner is responsible for
        blocker_tasks = df[
            (df["Owner"] == blocker_owner) &
            (df["Status"] != "Done")
        ]

        blocked_list = []
        total_impact = 0
        max_days = 0

        for _, row in owner_blocks.iterrows():
            due = row.get("Due_Date")
            days_blocked = 0
            if pd.notna(due):
                days_blocked = max(0, (datetime.now() - due).days)

            impact_val = row.get("Impact_Value", 0)
            if pd.notna(impact_val):
                total_impact += float(impact_val)

            max_days = max(max_days, days_blocked)

            blocked_list.append({
                "task_id": row["Task_ID"],
                "task": row["Task"],
                "dept": row["Department"],
                "owner": row["Owner"],
                "impact": row["Impact"],
                "days_blocked": days_blocked,
                "blocker": row.get("Blocker", ""),
            })

        if not blocked_list:
            continue

        # Determine severity
        critical_count = sum(1 for b in blocked_list if b["impact"] == "Critical")
        high_count = sum(1 for b in blocked_list if b["impact"] == "High")

        if critical_count > 0 or total_impact > 1000000 or max_days > 7:
            severity = "Critical"
        elif high_count > 1 or total_impact > 250000 or max_days > 3:
            severity = "High"
        else:
            severity = "Watch"

        # Find blocker task name
        blocker_task_name = "Multiple items"
        if not blocker_tasks.empty:
            blocker_task_name = blocker_tasks.iloc[0]["Task"]

        friction_points.append(FrictionPoint(
            blocker_task_id=blocker_tasks.iloc[0]["Task_ID"] if not blocker_tasks.empty else "",
            blocker_task=blocker_task_name,
            blocker_owner=blocker_owner,
            blocker_dept=blocker_tasks.iloc[0]["Department"] if not blocker_tasks.empty else "",
            blocked_tasks=blocked_list,
            blocked_count=len(blocked_list),
            total_impact_value=total_impact,
            max_days_blocked=max_days,
            severity=severity,
        ))

    # Sort by severity then impact
    severity_order = {"Critical": 0, "High": 1, "Watch": 2}
    friction_points.sort(key=lambda f: (severity_order.get(f.severity, 3), -f.total_impact_value))

    return friction_points


def analyze_owner_load(df: pd.DataFrame) -> List[OwnerLoad]:
    """Analyze workload per owner to detect overload."""
    loads = []

    for owner in df["Owner"].unique():
        owner_df = df[df["Owner"] == owner]
        open_work = owner_df[owner_df["Status"] != "Done"]

        if open_work.empty:
            continue

        overdue = open_work[open_work.get("overdue", False) == True]
        blocked = open_work[open_work.get("blocked", False) == True]
        high_impact = open_work[open_work.get("high_impact", False) == True]
        decisions = open_work[open_work.get("decision_required", False) == True]

        avg_score = open_work["attention_score"].mean() if len(open_work) > 0 else 0

        total_open = len(open_work)
        overdue_count = len(overdue)
        blocked_count = len(blocked)
        high_impact_count = len(high_impact)
        decisions_count = len(decisions)

        # Determine load level
        if total_open > 8 or overdue_count > 2 or (blocked_count > 2 and high_impact_count > 1):
            load_level = "Overloaded"
        elif total_open > 5 or overdue_count > 0 or blocked_count > 1:
            load_level = "High"
        elif total_open > 2:
            load_level = "Normal"
        else:
            load_level = "Light"

        dept = owner_df["Department"].iloc[0] if len(owner_df) > 0 else ""

        loads.append(OwnerLoad(
            owner=owner,
            department=dept,
            total_open=total_open,
            overdue=overdue_count,
            blocked=blocked_count,
            high_impact=high_impact_count,
            decisions_required=decisions_count,
            avg_attention_score=round(avg_score, 1),
            load_level=load_level,
        ))

    # Sort by load level severity then avg score
    level_order = {"Overloaded": 0, "High": 1, "Normal": 2, "Light": 3}
    loads.sort(key=lambda l: (level_order.get(l.load_level, 4), -l.avg_attention_score))

    return loads


def detect_systemic_risks(df: pd.DataFrame) -> List[SystemicRisk]:
    """Detect systemic patterns across the portfolio."""
    risks = []

    # 1. Recurring blocker pattern - same blocker appearing multiple times
    blockers = df[df.get("blocked", False) == True]["Blocker"].dropna()
    blockers = blockers[blockers.str.strip() != ""]
    blocker_counts = blockers.value_counts()

    for blocker, count in blocker_counts.items():
        if count >= 3:
            affected = df[
                (df.get("blocked", False) == True) &
                (df["Blocker"] == blocker)
            ]["Task_ID"].tolist()
            risks.append(SystemicRisk(
                pattern_type="recurring_blocker",
                description=f"Blocker '{blocker}' affects {count} items",
                affected_items=affected,
                severity="High" if count >= 5 else "Watch",
                recommendation=f"Address root cause of '{blocker}' - consider process change or dedicated owner",
            ))

    # 2. Owner overload
    owner_loads = analyze_owner_load(df)
    overloaded = [ol for ol in owner_loads if ol.load_level == "Overloaded"]
    for ol in overloaded:
        affected = df[
            (df["Owner"] == ol.owner) &
            (df["Status"] != "Done")
        ]["Task_ID"].tolist()
        risks.append(SystemicRisk(
            pattern_type="owner_overload",
            description=f"{ol.owner} has {ol.total_open} open items ({ol.overdue} overdue, {ol.blocked} blocked)",
            affected_items=affected,
            severity="Critical" if ol.overdue > 3 else "High",
            recommendation=f"Redistribute work from {ol.owner} or add capacity",
        ))

    # 3. Department risk concentration
    dept_risk = df[df.get("high_impact", False) == True].groupby("Department").size()
    total_high = len(df[df.get("high_impact", False) == True])
    for dept, count in dept_risk.items():
        if total_high > 0 and count / total_high > 0.4:  # >40% of high-impact in one dept
            affected = df[
                (df["Department"] == dept) &
                (df.get("high_impact", False) == True)
            ]["Task_ID"].tolist()
            risks.append(SystemicRisk(
                pattern_type="dept_concentration",
                description=f"{dept} holds {count}/{total_high} high-impact items ({count/total_high*100:.0f}%)",
                affected_items=affected,
                severity="High",
                recommendation=f"Review {dept} capacity and risk distribution",
            ))

    # 4. Stale cluster - multiple stale items in same department
    stale = df[df.get("stale", False) == True]
    stale_by_dept = stale.groupby("Department").size()
    for dept, count in stale_by_dept.items():
        if count >= 3:
            affected = stale[stale["Department"] == dept]["Task_ID"].tolist()
            risks.append(SystemicRisk(
                pattern_type="stale_cluster",
                description=f"{dept} has {count} stale items (>48h no update)",
                affected_items=affected,
                severity="Watch",
                recommendation=f"Request status updates from {dept} owners",
            ))

    # 5. Dependency chain risk - long dependency chains
    dep_chains = _find_dependency_chains(df)
    for chain in dep_chains:
        if len(chain) >= 3:
            risks.append(SystemicRisk(
                pattern_type="dependency_chain",
                description=f"Dependency chain of {len(chain)} items: {' → '.join(chain)}",
                affected_items=chain,
                severity="High",
                recommendation="Review chain for single points of failure; consider parallelizing",
            ))

    return risks


def _find_dependency_chains(df: pd.DataFrame) -> List[List[str]]:
    """Find dependency chains in the task graph."""
    # Build adjacency list
    graph = defaultdict(list)
    for _, row in df.iterrows():
        dep = row.get("Dependency", "")
        if isinstance(dep, str) and dep.strip():
            graph[dep.strip()].append(row["Task_ID"])

    # Find chains (simple DFS)
    chains = []
    visited = set()

    def dfs(node: str, path: List[str]):
        if node in visited or node not in graph:
            if len(path) >= 2:
                chains.append(path.copy())
            return
        visited.add(node)
        path.append(node)
        for next_node in graph[node]:
            dfs(next_node, path)
        path.pop()
        visited.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node, [])

    # Filter and deduplicate
    unique_chains = []
    for chain in chains:
        if len(chain) >= 3:
            chain_ids = tuple(chain)
            if chain_ids not in unique_chains:
                unique_chains.append(chain_ids)

    return [list(c) for c in unique_chains]


def generate_meeting_brief(
    df: pd.DataFrame,
    meeting_name: str = "",
    meeting_date: datetime = None,
    focus_departments: List[str] = None,
    focus_owners: List[str] = None,
) -> Dict[str, Any]:
    """Generate an intelligent, agenda-ready meeting brief."""

    if meeting_date is None:
        meeting_date = datetime.now()

    # Filter by focus if provided
    brief_df = df.copy()
    if focus_departments:
        brief_df = brief_df[brief_df["Department"].isin(focus_departments)]
    if focus_owners:
        brief_df = brief_df[brief_df["Owner"].isin(focus_owners)]

    # Only open work
    brief_df = brief_df[brief_df["Status"] != "Done"]

    # Categorize items
    decisions = brief_df[brief_df.get("decision_required", False) == True].copy()
    critical_risk = brief_df[
        (brief_df.get("attention_score", 0) >= 10) &
        (brief_df["Status"] != "Done")
    ].copy()
    high_risk = brief_df[
        (brief_df.get("attention_score", 0) >= 7) &
        (brief_df.get("attention_score", 0) < 10) &
        (brief_df["Status"] != "Done")
    ].copy()
    blocked = brief_df[brief_df.get("blocked", False) == True].copy()
    overdue = brief_df[brief_df.get("overdue", False) == True].copy()

    # Sort each category
    decisions = decisions.sort_values(["attention_score", "Due_Date"], ascending=[False, True])
    critical_risk = critical_risk.sort_values(["attention_score", "Due_Date"], ascending=[False, True])
    high_risk = high_risk.sort_values(["attention_score", "Due_Date"], ascending=[False, True])
    blocked = blocked.sort_values(["attention_score", "Due_Date"], ascending=[False, True])
    overdue = overdue.sort_values(["attention_score", "Due_Date"], ascending=[False, True])

    # Friction points
    friction = detect_cross_team_friction(brief_df)

    # Systemic risks
    systemic = detect_systemic_risks(brief_df)

    # Owner loads (overloaded only)
    overloaded_owners = [ol for ol in analyze_owner_load(brief_df) if ol.load_level in ["Overloaded", "High"]]

    return {
        "meeting_name": meeting_name,
        "meeting_date": meeting_date.strftime("%Y-%m-%d %H:%M"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "total_open": len(brief_df),
            "decisions_required": len(decisions),
            "critical_risk": len(critical_risk),
            "high_risk": len(high_risk),
            "blocked": len(blocked),
            "overdue": len(overdue),
            "friction_points": len(friction),
            "systemic_risks": len(systemic),
            "overloaded_owners": len(overloaded_owners),
        },
        "decisions": decisions.to_dict("records"),
        "critical_risk": critical_risk.to_dict("records"),
        "high_risk": high_risk.to_dict("records"),
        "blocked": blocked.to_dict("records"),
        "overdue": overdue.to_dict("records"),
        "friction_points": [
            {
                "blocker_owner": f.blocker_owner,
                "blocker_dept": f.blocker_dept,
                "blocked_count": f.blocked_count,
                "total_impact": f.total_impact_value,
                "max_days_blocked": f.max_days_blocked,
                "severity": f.severity,
                "blocked_tasks": f.blocked_tasks,
            }
            for f in friction
        ],
        "systemic_risks": [
            {
                "type": s.pattern_type,
                "description": s.description,
                "severity": s.severity,
                "recommendation": s.recommendation,
                "affected_count": len(s.affected_items),
            }
            for s in systemic
        ],
        "owner_loads": [
            {
                "owner": ol.owner,
                "dept": ol.department,
                "open": ol.total_open,
                "overdue": ol.overdue,
                "blocked": ol.blocked,
                "decisions": ol.decisions_required,
                "avg_score": ol.avg_attention_score,
                "level": ol.load_level,
            }
            for ol in overloaded_owners
        ],
    }


def get_executive_attention_queue(
    df: pd.DataFrame,
    max_items: int = 7,
    min_band: str = "High",  # Only Critical and High on executive home screen
) -> pd.DataFrame:
    """Get the executive attention queue - only Critical/High bands."""
    band_threshold = {"Critical": 10, "High": 7, "Watch": 4, "Normal": 0}
    min_score = band_threshold.get(min_band, 7)

    filtered = df[
        (df["attention_score"] >= min_score) &
        (df["Status"] != "Done")
    ].copy()

    return rank_attention(filtered).head(max_items)


def get_decision_queue_detailed(df: pd.DataFrame) -> pd.DataFrame:
    """Get decision queue with enhanced context for executives."""
    decisions = df[df.get("decision_required", False) == True].copy()
    if decisions.empty:
        return decisions

    # Add decision urgency
    def decision_urgency(row):
        if row.get("overdue", False):
            return "URGENT - Overdue"
        due = row.get("Due_Date")
        if pd.notna(due):
            days = (due - pd.Timestamp.now()).days
            if days <= 0:
                return "URGENT - Due today"
            elif days <= 2:
                return f"Due in {days} day(s)"
            elif days <= 7:
                return f"Due in {days} days"
        return "No deadline"

    decisions["decision_urgency"] = decisions.apply(decision_urgency, axis=1)

    # Add impact context
    decisions["impact_context"] = decisions.apply(
        lambda r: f"{r.get('Impact', '')} impact" + (f" (${r.get('Impact_Value', 0):,.0f})" if pd.notna(r.get('Impact_Value')) and r.get('Impact_Value', 0) > 0 else ""),
        axis=1
    )

    return decisions.sort_values(["attention_score", "Due_Date"], ascending=[False, True]).reset_index(drop=True)


def get_blocked_friction_detailed(df: pd.DataFrame) -> Dict[str, Any]:
    """Get detailed blocked/friction analysis with cross-team view."""
    blocked = df[df.get("blocked", False) == True].copy()
    if blocked.empty:
        return {"by_department": {}, "by_blocker_owner": {}, "cross_team": [], "summary": {}}

    # By department
    by_dept = {}
    for dept in sorted(blocked["Department"].unique()):
        dept_blocked = blocked[blocked["Department"] == dept]
        by_dept[dept] = {
            "count": len(dept_blocked),
            "items": dept_blocked.sort_values("attention_score", ascending=False).to_dict("records"),
        }

    # By blocker owner (who is blocking)
    by_blocker_owner = {}
    for owner in blocked["Blocker_Owner"].dropna().unique():
        if not str(owner).strip():
            continue
        owner_blocked = blocked[blocked["Blocker_Owner"] == owner]
        by_blocker_owner[owner] = {
            "count": len(owner_blocked),
            "blocker_dept": owner_blocked["Department"].iloc[0] if len(owner_blocked) > 0 else "",
            "items": owner_blocked.sort_values("attention_score", ascending=False).to_dict("records"),
        }

    # Cross-team friction
    friction = detect_cross_team_friction(df)

    return {
        "by_department": by_dept,
        "by_blocker_owner": by_blocker_owner,
        "cross_team": [
            {
                "blocker_owner": f.blocker_owner,
                "blocker_dept": f.blocker_dept,
                "blocked_count": f.blocked_count,
                "total_impact": f.total_impact_value,
                "max_days_blocked": f.max_days_blocked,
                "severity": f.severity,
                "blocked_tasks": f.blocked_tasks,
            }
            for f in friction
        ],
        "summary": {
            "total_blocked": len(blocked),
            "departments_affected": len(by_dept),
            "blocker_owners": len(by_blocker_owner),
            "cross_team_friction_points": len(friction),
        },
    }


def get_org_pulse_enhanced(df: pd.DataFrame) -> pd.DataFrame:
    """Enhanced org pulse with risk percentages and trends."""
    metrics = []

    for dept in sorted(df["Department"].unique()):
        dept_df = df[df["Department"] == dept]
        open_work = dept_df[dept_df["Status"] != "Done"]
        done_work = dept_df[dept_df["Status"] == "Done"]

        total_work = len(dept_df)
        open_count = len(open_work)

        if open_count == 0:
            continue

        overdue = open_work[open_work.get("overdue", False) == True]
        blocked = open_work[open_work.get("blocked", False) == True]
        high_impact = open_work[open_work.get("high_impact", False) == True]
        stale = open_work[open_work.get("stale", False) == True]
        decisions = open_work[open_work.get("decision_required", False) == True]

        overdue_pct = round(len(overdue) / open_count * 100, 1) if open_count > 0 else 0
        blocked_pct = round(len(blocked) / open_count * 100, 1) if open_count > 0 else 0
        stale_pct = round(len(stale) / open_count * 100, 1) if open_count > 0 else 0

        # Completion rate
        completion_rate = round(len(done_work) / total_work * 100, 1) if total_work > 0 else 0

        # Average days to complete (for done items)
        avg_days_to_complete = 0
        if len(done_work) > 0:
            done_with_dates = done_work[
                done_work["Start_Date"].notna() & done_work["Completed_Date"].notna()
            ]
            if len(done_with_dates) > 0:
                avg_days_to_complete = round(
                    (done_with_dates["Completed_Date"] - done_with_dates["Start_Date"]).dt.days.mean(), 1
                )

        # Risk score for department (0-100)
        risk_score = min(100, (
            overdue_pct * 2 +
            blocked_pct * 3 +
            stale_pct * 1 +
            len(high_impact) * 5 +
            len(decisions) * 3
        ))

        metrics.append({
            "Department": dept,
            "Total": total_work,
            "Open": open_count,
            "Done": len(done_work),
            "Completion_Rate": f"{completion_rate}%",
            "Avg_Days_to_Complete": avg_days_to_complete,
            "Overdue": len(overdue),
            "Overdue_Pct": f"{overdue_pct}%",
            "Blocked": len(blocked),
            "Blocked_Pct": f"{blocked_pct}%",
            "High_Impact": len(high_impact),
            "Stale": len(stale),
            "Stale_Pct": f"{stale_pct}%",
            "Decisions": len(decisions),
            "Avg_Attention_Score": round(open_work["attention_score"].mean(), 1) if open_count > 0 else 0,
            "Risk_Score": round(risk_score, 1),
        })

    result = pd.DataFrame(metrics)
    if not result.empty:
        result = result.sort_values("Risk_Score", ascending=False).reset_index(drop=True)

    return result


# Re-export rank_attention for convenience
from app.engine.rule_engine import rank_attention


# ---------------------------------------------------------------------------
# Persona lens — viewer-aware grouping over the engine ranking.
# Scores and order are never changed here; items are only grouped into
# "for you" (viewer departments) and "also on your radar" (rest of org).
# ---------------------------------------------------------------------------

PERSONAS = {
    "CEO": None,  # full-organization view
    "Chief of Staff": None,  # full-organization view
    "CMO": ["Marketing", "Sales"],
    "CFO": ["Finance", "Legal"],
    "CTO / CPO": ["Technology", "Product"],
    "COO": ["Operations", "Technology", "People"],
}


def persona_departments(persona: str | None) -> list | None:
    """Departments in a viewer's scope. None means the whole organization."""
    if not persona:
        return None
    return PERSONAS.get(persona)


def persona_relevant(df: pd.DataFrame, persona: str | None, max_items: int = 3) -> pd.DataFrame:
    """Top engine-ranked open items inside the viewer's departments."""
    departments = persona_departments(persona)
    if not departments:
        return df.iloc[0:0]
    subset = df[(df["Department"].isin(departments)) & (df["Status"] != "Done")]
    return rank_attention(subset).head(max_items)


# ---------------------------------------------------------------------------
# Custom focus profile — freeform "what I care about" matching.
# Plain keyword overlap with title-weighted, prefix-tolerant matching.
# No LLM, no scoring changes: relevance only groups the engine ranking.
# ---------------------------------------------------------------------------

PROFILE_STOPWORDS = frozenset("""
    i me my we our you your he she it they them his her its their
    am is are was were be been being have has had do does did will
    would can could should shall may might must a an the and or but
    of on in to for with as at by from that this these those then
    so such no not only also very include includes including things
    thing stuff priorities priority chief officer head like want need
    needs look looking tell show give get please hello hey
""".split())

# field → weight for one distinct keyword hit (strongest field wins per keyword)
PROFILE_FIELDS = (
    ("Task", 3),
    ("Project", 2),
    ("Department", 2),
    ("Decision_Requested", 2),
    ("Blocker", 1),
    ("Notes", 1),
    ("Owner", 1),
    ("Owner_Role", 1),
)

MAX_PROFILE_KEYWORDS = 12


def _norm_tokens(text: Any) -> List[str]:
    return [
        cleaned for token in re.split(r"[^A-Za-z0-9]+", str(text or ""))
        if (cleaned := re.sub(r"[^a-z0-9]", "", token.lower()))
    ]


def _tok_match(keyword: str, token: str) -> bool:
    """Prefix-tolerant match ('launch' hits 'launches'); longer keywords
    also match inside words ('brand' hits 'rebranding')."""
    if len(keyword) < 3 or len(token) < 3:
        return False
    if token.startswith(keyword) or keyword.startswith(token):
        return True
    return len(keyword) >= 5 and keyword in token


def extract_profile_keywords(text: str | None) -> List[str]:
    """Meaningful keywords from freeform focus text, order-preserved."""
    keywords: List[str] = []
    for token in _norm_tokens(text):
        if len(token) < 2 or token in PROFILE_STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
        if len(keywords) >= MAX_PROFILE_KEYWORDS:
            break
    return keywords


def profile_relevance(row: pd.Series, keywords: List[str]) -> Tuple[int, List[str]]:
    """Relevance score + matched terms for one row. Score only groups output."""
    if not keywords:
        return 0, []
    field_tokens = {field: _norm_tokens(row.get(field)) for field, _ in PROFILE_FIELDS}
    score = 0
    matched: List[str] = []
    for keyword in keywords:
        best = 0
        for field, weight in PROFILE_FIELDS:
            if any(_tok_match(keyword, token) for token in field_tokens[field]):
                best = max(best, weight)
        if best:
            score += best
            matched.append(keyword)
    return score, matched