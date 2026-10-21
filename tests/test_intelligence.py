"""
Intelligence layer tests: friction, owner load, systemic risk, org pulse,
meeting brief, persona lens and focus profile.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from app.engine.intelligence import (
    PERSONAS,
    analyze_owner_load,
    detect_cross_team_friction,
    detect_systemic_risks,
    extract_profile_keywords,
    generate_meeting_brief,
    get_blocked_friction_detailed,
    get_decision_queue_detailed,
    get_executive_attention_queue,
    get_org_pulse_enhanced,
    persona_departments,
    profile_relevance,
)
from app.engine.rule_engine import compute_all_flags, rank_attention
from helpers import make_row


def frame(reference, rows):
    return pd.DataFrame([make_row(reference, **r) for r in rows])


# ---------------------------------------------------------------------------
# Cross-team friction
# ---------------------------------------------------------------------------

def test_friction_detected_when_owner_blocks_others(today):
    rows = [
        {"Task_ID": "B-1", "Owner": "Legal", "Department": "Legal", "Status": "Blocked",
         "Blocker": "Contract review", "Blocker_Owner": "Legal", "Impact": "Critical"},
        {"Task_ID": "X-1", "Owner": "Sales", "Department": "Sales", "Status": "In Progress",
         "Blocker": "Contract review", "Blocker_Owner": "Legal", "Impact": "High"},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    friction = detect_cross_team_friction(df)
    assert friction, "expected a friction point"
    point = friction[0]
    assert point.blocker_owner == "Legal"
    assert point.blocked_count == 2
    assert point.severity == "Critical"


def test_no_friction_without_blocker_owner(today):
    rows = [{"Task_ID": "X-1", "Status": "Blocked", "Blocker": "Something", "Blocker_Owner": ""}]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    assert detect_cross_team_friction(df) == []


# ---------------------------------------------------------------------------
# Owner load
# ---------------------------------------------------------------------------

def test_owner_overload_detected(today):
    rows = [
        {"Task_ID": f"O-{i}", "Owner": "Busy", "Department": "Ops",
         "Status": "In Progress", "Impact": "High"}
        for i in range(9)
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    loads = {l.owner: l for l in analyze_owner_load(df)}
    assert loads["Busy"].load_level == "Overloaded"
    assert loads["Busy"].total_open == 9


def test_light_owner_not_flagged(today):
    rows = [{"Task_ID": "O-1", "Owner": "Calm", "Department": "Ops", "Status": "In Progress"}]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    loads = {l.owner: l for l in analyze_owner_load(df)}
    assert loads["Calm"].load_level == "Light"


# ---------------------------------------------------------------------------
# Systemic risk
# ---------------------------------------------------------------------------

def test_recurring_blocker_pattern_detected(today):
    rows = [
        {"Task_ID": f"R-{i}", "Status": "Blocked", "Blocker": "Same cause",
         "Blocker_Owner": "Someone"}
        for i in range(3)
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    risks = detect_systemic_risks(df)
    assert any(r.pattern_type == "recurring_blocker" for r in risks)


def test_dependency_chain_detected(today):
    rows = [
        {"Task_ID": "C-1", "Dependency": "C-2"},
        {"Task_ID": "C-2", "Dependency": "C-3"},
        {"Task_ID": "C-3"},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    risks = detect_systemic_risks(df)
    chains = [r for r in risks if r.pattern_type == "dependency_chain"]
    assert chains
    assert len(chains[0].affected_items) >= 3


# ---------------------------------------------------------------------------
# Org pulse
# ---------------------------------------------------------------------------

def test_org_pulse_aggregates_by_department(today):
    rows = [
        {"Task_ID": "A-1", "Department": "Sales", "Owner": "S1", "Status": "In Progress"},
        {"Task_ID": "A-2", "Department": "Sales", "Owner": "S2", "Status": "Blocked", "Blocker": "x"},
        {"Task_ID": "B-1", "Department": "Tech", "Owner": "T1", "Status": "In Progress"},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    org = get_org_pulse_enhanced(df).set_index("Department")
    assert org.loc["Sales", "Open"] == 2
    assert org.loc["Sales", "Blocked"] == 1
    assert org.loc["Tech", "Open"] == 1


def test_org_pulse_omits_departments_with_no_open_work(today):
    rows = [{"Task_ID": "B-1", "Department": "Tech", "Owner": "T1", "Status": "Done"}]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    org = get_org_pulse_enhanced(df)
    assert "Tech" not in set(org["Department"])


def test_org_pulse_risk_score_discriminates(today):
    """A healthy department must score materially below a failing one."""
    rows = [
        {"Task_ID": "H-1", "Department": "Healthy", "Owner": "H", "Status": "In Progress",
         "Impact": "Low"},
        {"Task_ID": "U-1", "Department": "Unhealthy", "Owner": "U", "Status": "Blocked",
         "Blocker": "x", "Impact": "Critical", "Executive_Decision_Required": True},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    org = get_org_pulse_enhanced(df).set_index("Department")
    assert org.loc["Unhealthy", "Risk_Score"] > org.loc["Healthy", "Risk_Score"]
    assert org.loc["Healthy", "Risk_Score"] < 50


def test_org_pulse_at_risk_counted_once_per_item(today):
    """An item that is both overdue and high impact counts once, not twice."""
    rows = [
        {"Task_ID": "A-1", "Department": "Sales", "Owner": "S", "Status": "In Progress",
         "Impact": "Critical", "Due_Date": today - timedelta(days=3)},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    org = get_org_pulse_enhanced(df).set_index("Department")
    assert org.loc["Sales", "At_Risk"] == 1


# ---------------------------------------------------------------------------
# Decision queue + meeting brief
# ---------------------------------------------------------------------------

def test_decision_queue_derives_urgency(today):
    rows = [
        {"Task_ID": "D-1", "Executive_Decision_Required": True, "Due_Date": today},
        {"Task_ID": "D-2", "Executive_Decision_Required": True, "Due_Date": today - timedelta(days=1)},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    decisions = get_decision_queue_detailed(df, today).set_index("Task_ID")
    assert decisions.loc["D-2", "decision_urgency"].startswith("URGENT")
    assert decisions.loc["D-1", "decision_urgency"].startswith("URGENT")


def test_decision_urgency_uses_the_reference_clock(today):
    """A due date in the past must read as overdue, not "due today".

    The urgency label previously used the wall clock, so a decision due
    days ago was labelled "URGENT - Due today".
    """
    rows = [
        {"Task_ID": "D-1", "Executive_Decision_Required": True,
         "Due_Date": today - timedelta(days=5)},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    urgency = get_decision_queue_detailed(df, today).iloc[0]["decision_urgency"]
    assert urgency == "URGENT - Overdue"


def test_decision_urgency_is_independent_of_when_it_is_called(today):
    """The label must not change with the real clock."""
    rows = [
        {"Task_ID": "D-1", "Executive_Decision_Required": True,
         "Due_Date": today + timedelta(days=3)},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    first = get_decision_queue_detailed(df, today).iloc[0]["decision_urgency"]
    second = get_decision_queue_detailed(df, today).iloc[0]["decision_urgency"]
    assert first == second == "Due in 3 days"


def test_meeting_brief_sections_present(today):
    rows = [
        {"Task_ID": "D-1", "Executive_Decision_Required": True, "Impact": "Critical"},
        {"Task_ID": "B-1", "Status": "Blocked", "Blocker": "x", "Blocker_Owner": "Legal"},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    brief = generate_meeting_brief(df, meeting_name="Q3 Board Review")
    assert brief["meeting_name"] == "Q3 Board Review"
    assert brief["summary"]["decisions_required"] >= 1
    assert brief["summary"]["blocked"] >= 1
    assert "decisions" in brief and "critical_risk" in brief


def test_meeting_brief_respects_focus(today):
    rows = [
        {"Task_ID": "D-1", "Department": "Sales", "Executive_Decision_Required": True},
        {"Task_ID": "D-2", "Department": "Tech", "Executive_Decision_Required": True},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    brief = generate_meeting_brief(df, focus_departments=["Sales"])
    assert brief["summary"]["decisions_required"] == 1


# ---------------------------------------------------------------------------
# Attention queue
# ---------------------------------------------------------------------------

def test_executive_attention_queue_only_high_band(today):
    rows = [
        {"Task_ID": "C-1", "Impact": "Critical", "Executive_Decision_Required": True},
        {"Task_ID": "N-1", "Impact": "Low"},
    ]
    df = rank_attention(compute_all_flags(frame(today, rows)))
    queue = get_executive_attention_queue(df, max_items=10, min_band="High")
    assert "N-1" not in set(queue["Task_ID"])
    assert "C-1" in set(queue["Task_ID"])


# ---------------------------------------------------------------------------
# Persona lens
# ---------------------------------------------------------------------------

def test_persona_scopes():
    assert persona_departments("CEO") is None
    assert persona_departments("Chief of Staff") is None
    assert persona_departments("CMO") == ["Marketing", "Sales"]
    assert persona_departments("CTO / CPO") == ["Technology", "Product"]


def test_persona_never_changes_scores(scored_df):
    """Grouping only — the underlying ranking is untouched."""
    from app.engine.rule_engine import rank_attention

    baseline = rank_attention(scored_df)
    for persona in PERSONAS:
        subset = scored_df[
            (scored_df["Department"].isin(persona_departments(persona) or scored_df["Department"].unique()))
            & (scored_df["Status"] != "Done")
        ]
        # Re-ranking the subset preserves the global order of its members.
        assert list(rank_attention(subset)["Task_ID"]) == [
            t for t in baseline["Task_ID"] if t in set(subset["Task_ID"])
        ]


# ---------------------------------------------------------------------------
# Focus profile
# ---------------------------------------------------------------------------

def test_profile_keyword_extraction():
    keywords = extract_profile_keywords("brand launches, partnerships, customer escalations")
    assert "brand" in keywords
    assert "launches" in keywords
    assert "partnerships" in keywords


def test_profile_extraction_drops_stopwords():
    keywords = extract_profile_keywords("I want the brand and the teams")
    assert "brand" in keywords
    assert "and" not in keywords
    assert "the" not in keywords


def test_profile_match_is_title_weighted():
    row = make_row(pd.Timestamp.now(), Task="Brand launch campaign", Project="Other")
    score_task, matched = profile_relevance(row, ["brand"])
    assert score_task > 0
    assert "brand" in matched


def test_profile_no_match_returns_zero():
    row = make_row(pd.Timestamp.now(), Task="Unrelated task", Project="Other")
    score, matched = profile_relevance(row, ["zeppelin"])
    assert score == 0
    assert matched == []


def test_profile_prefix_tolerant_matching():
    row = make_row(pd.Timestamp.now(), Task="Launch the rebrand project")
    score, matched = profile_relevance(row, ["launch"])
    assert score > 0
    assert "launch" in matched


def test_profile_does_not_match_a_shorter_shared_prefix():
    """'marketing' must not match 'market'.

    Otherwise a task titled 'India market launch' would land in a
    Marketing exec's focus queue.
    """
    row = make_row(pd.Timestamp.now(), Task="India market launch partner approval")
    score, matched = profile_relevance(row, ["marketing"])
    assert score == 0
    assert matched == []


def test_profile_matches_keyword_inside_a_longer_word():
    row = make_row(pd.Timestamp.now(), Task="Full rebranding programme")
    score, matched = profile_relevance(row, ["brand"])
    assert score > 0
    assert "brand" in matched


# ---------------------------------------------------------------------------
# Sample dataset integrity
# ---------------------------------------------------------------------------

def test_sample_departments_documented(scored_df):
    """README documents the department count; keep code and docs in step."""
    assert scored_df["Department"].nunique() == 10


def test_sample_has_dependency_graph(scored_df):
    """Dependency risk must be demonstrable with the bundled dataset."""
    assert scored_df["Dependency"].astype(str).str.strip().ne("").sum() > 0
    assert int(scored_df["dependency_risk"].sum()) > 0
