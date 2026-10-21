"""
Rule engine contract tests.

These assert the exact flag/score semantics the executive UI depends on.
Any change here changes what an executive sees — so each rule is pinned.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from app.engine.rule_engine import (
    compute_all_flags,
    compute_flags,
    count_attention,
    get_at_risk,
    get_attention_queue,
    get_decision_queue,
    rank_attention,
)
from helpers import make_row


def flags_for(row: pd.Series):
    return compute_flags(row, pd.DataFrame([row]), row.get("_reference", pd.Timestamp.now()))


def test_overdue_only_when_due_date_is_in_the_past(today):
    row = make_row(today, Due_Date=today - timedelta(days=1))
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.overdue is True
    assert result.at_risk is False
    assert result.attention_score == 4
    assert "Overdue" in result.reason_codes


def test_due_today_is_not_overdue(today):
    """A task due today is due today, never overdue — even late at night."""
    row = make_row(today, Due_Date=today)
    late = today.replace(hour=23, minute=59)
    result = compute_flags(row, pd.DataFrame([row]), late)
    assert result.overdue is False
    assert result.at_risk is True
    assert result.attention_score == 2


def test_at_risk_window_is_today_through_two_days(today):
    for offset, expected in ((0, True), (1, True), (2, True), (3, False)):
        row = make_row(today, Due_Date=today + timedelta(days=offset))
        result = compute_flags(row, pd.DataFrame([row]), today)
        assert result.at_risk is expected, f"offset={offset}"


def test_done_items_are_never_flagged(today):
    row = make_row(
        today,
        Status="Done",
        Due_Date=today - timedelta(days=30),
        Last_Updated=today - timedelta(days=60),
    )
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.overdue is False
    assert result.at_risk is False
    assert result.stale is False
    assert result.attention_score == 0
    assert result.score_band == "Normal"


def test_stale_uses_strictly_greater_than_48h(today):
    exactly = make_row(today, Last_Updated=today - timedelta(hours=48))
    assert compute_flags(exactly, pd.DataFrame([exactly]), today).stale is False

    over = make_row(today, Last_Updated=today - timedelta(hours=48, minutes=1))
    assert compute_flags(over, pd.DataFrame([over]), today).stale is True


def test_blocked_from_status_or_blocker_column(today):
    by_status = make_row(today, Status="Blocked")
    assert compute_flags(by_status, pd.DataFrame([by_status]), today).blocked is True

    by_column = make_row(today, Blocker="Waiting on vendor")
    assert compute_flags(by_column, pd.DataFrame([by_column]), today).blocked is True


def test_decision_required_scores_five(today):
    row = make_row(today, Executive_Decision_Required=True)
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.decision_required is True
    assert result.attention_score == 5


def test_impact_scores_critical_five_high_three(today):
    critical = make_row(today, Impact="Critical")
    assert compute_flags(critical, pd.DataFrame([critical]), today).attention_score == 5

    high = make_row(today, Impact="High")
    assert compute_flags(high, pd.DataFrame([high]), today).attention_score == 3


def test_dependency_risk_when_dependency_is_blocked(today):
    dep = make_row(today, Task_ID="D-1", Status="Blocked", Due_Date=today + timedelta(days=5))
    dependent = make_row(today, Task_ID="X-1", Dependency="D-1")
    frame = pd.DataFrame([dep, dependent])
    result = compute_flags(dependent, frame, today)
    assert result.dependency_risk is True
    assert result.attention_score == 2


def test_dependency_risk_when_dependency_is_overdue(today):
    dep = make_row(today, Task_ID="D-1", Status="In Progress", Due_Date=today - timedelta(days=1))
    dependent = make_row(today, Task_ID="X-1", Dependency="D-1")
    frame = pd.DataFrame([dep, dependent])
    assert compute_flags(dependent, frame, today).dependency_risk is True


def test_dependency_risk_supports_multiple_dependency_ids(today):
    dep_a = make_row(today, Task_ID="D-1", Status="Blocked", Due_Date=today + timedelta(days=5))
    dep_b = make_row(today, Task_ID="D-2", Status="In Progress", Due_Date=today + timedelta(days=5))
    dependent = make_row(today, Task_ID="X-1", Dependency="D-1;D-2")
    frame = pd.DataFrame([dep_a, dep_b, dependent])
    result = compute_flags(dependent, frame, today)
    assert result.dependency_risk is True
    assert any("D-1" in code for code in result.reason_codes)


def test_healthy_dependency_is_not_a_risk(today):
    dep = make_row(today, Task_ID="D-1", Status="In Progress", Due_Date=today + timedelta(days=5))
    dependent = make_row(today, Task_ID="X-1", Dependency="D-1")
    frame = pd.DataFrame([dep, dependent])
    assert compute_flags(dependent, frame, today).dependency_risk is False


@pytest.mark.parametrize(
    "setup,expected_score",
    [
        ({"Executive_Decision_Required": True, "Impact": "Critical"}, 10),
        ({"Status": "Blocked"}, 4),
        ({"Status": "Blocked", "Impact": "Critical"}, 9),
        ({"Status": "Blocked", "Impact": "High"}, 7),
        ({"Executive_Decision_Required": True, "Status": "Blocked", "Impact": "High"}, 12),
    ],
)
def test_composite_scores(today, setup, expected_score):
    row = make_row(today, **setup)
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.attention_score == expected_score


@pytest.mark.parametrize(
    "score,band,setup",
    [
        (0, "Normal", {}),
        (3, "Normal", {"Impact": "High"}),
        (4, "Watch", {"Status": "Blocked"}),
        (5, "Watch", {"Impact": "Critical"}),
        (7, "High", {"Status": "Blocked", "Impact": "High"}),
        (9, "High", {"Status": "Blocked", "Impact": "Critical"}),
        (10, "Critical", {"Executive_Decision_Required": True, "Impact": "Critical"}),
        (12, "Critical", {"Executive_Decision_Required": True, "Status": "Blocked", "Impact": "High"}),
    ],
)
def test_score_bands(today, score, band, setup):
    """Band boundaries: 10+ Critical, 7-9 High, 4-6 Watch, 0-3 Normal."""
    row = make_row(today, **setup)
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.attention_score == score
    assert result.score_band == band


def test_score_band_boundaries_at_risk_overlap(today):
    """Blocked + due within 48h scores 6 (Watch), not 4."""
    row = make_row(today, Status="Blocked", Due_Date=today + timedelta(days=1))
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.attention_score == 6
    assert result.score_band == "Watch"


def test_score_band_boundary_overdue_and_critical(today):
    """Blocked + Critical + overdue scores 13 (Critical)."""
    row = make_row(today, Status="Blocked", Impact="Critical", Due_Date=today - timedelta(days=1))
    result = compute_flags(row, pd.DataFrame([row]), today)
    assert result.attention_score == 13
    assert result.score_band == "Critical"


def test_ranking_is_score_desc_then_due_asc(today):
    rows = [
        make_row(today, Task_ID="A", Impact="High", Due_Date=today + timedelta(days=30)),
        make_row(today, Task_ID="B", Impact="Critical", Due_Date=today + timedelta(days=9)),
        make_row(today, Task_ID="C", Impact="Critical", Due_Date=today + timedelta(days=3)),
    ]
    frame = pd.DataFrame(rows)
    ranked = rank_attention(compute_all_flags(frame))
    # B and C tie on score (5); the earlier due date wins.
    assert list(ranked["Task_ID"]) == ["C", "B", "A"]
    assert list(ranked["attention_score"]) == [5, 5, 3]


def test_count_attention_is_not_capped(today):
    """Headline counts must report every qualifying item, not the top N."""
    rows = [make_row(today, Task_ID=f"T{i}", Impact="High", Blocker="x") for i in range(20)]
    frame = compute_all_flags(pd.DataFrame(rows))
    assert len(get_attention_queue(frame, top_n=7)) == 7
    assert count_attention(frame) == 20


def test_sample_dataset_has_a_realistic_mix(scored_df):
    """The demo dataset must not present every item as a crisis."""
    assert len(scored_df) == 30
    assert 0 < int(scored_df["overdue"].sum()) < scored_df["Status"].ne("Done").sum()
    assert int(scored_df["stale"].sum()) < len(scored_df)
    assert int(scored_df["decision_required"].sum()) > 0
    assert int((scored_df["Status"] == "Done").sum()) > 0
    bands = scored_df["score_band"].value_counts().to_dict()
    assert bands.get("Normal", 0) > 0, "sample data should include healthy work"


def test_at_risk_view_matches_engine_rule(scored_df):
    """At Risk is one rule, applied once."""
    from app.components.ui import render_at_risk  # import guard only

    engine_view = get_at_risk(scored_df)
    expected = scored_df[
        (scored_df["at_risk"] == True)
        | ((scored_df["high_impact"] == True) & (scored_df["Status"] != "Done"))
    ]
    assert len(engine_view) == len(expected)
