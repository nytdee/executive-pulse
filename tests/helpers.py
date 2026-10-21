"""Test helpers shared across the Executive Pulse test suite."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def make_row(reference: datetime, **overrides) -> pd.Series:
    """Build a single task row with sensible defaults for flag testing."""
    base = {
        "Task_ID": "X-001",
        "Task": "Test task",
        "Project": "Test project",
        "Department": "Testing",
        "Owner": "Tester",
        "Status": "In Progress",
        "Priority": "Medium",
        "Start_Date": reference - timedelta(days=5),
        "Due_Date": reference + timedelta(days=10),
        "Completed_Date": None,
        "Impact": "Low",
        "Impact_Value": 0,
        "Blocker": "",
        "Dependency": "",
        "Blocker_Owner": "",
        "Last_Updated": reference,
        "Executive_Decision_Required": False,
        "Decision_By": None,
        "Decision_Requested": "",
        "Source_URL": "",
        "Notes": "",
    }
    base.update(overrides)
    return pd.Series(base)


def make_frame(reference: datetime, rows: list) -> pd.DataFrame:
    """Build a DataFrame from keyword rows (each a dict of overrides)."""
    return pd.DataFrame([make_row(reference, **r) for r in rows])
