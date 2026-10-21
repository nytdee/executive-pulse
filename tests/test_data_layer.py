"""
Data layer tests: schema validation, normalisation, mapping and ingestion.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from app.data.loader import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    DataValidationError,
    load_and_validate,
    normalize_data,
    validate_columns,
    validate_data,
)
from app.data.mapping import (
    apply_mapping,
    find_unknown_values,
    mapping_status,
    process_mapped_frame,
    scope_key,
    suggest_column_mapping,
    suggest_value_mapping,
)
from tests.helpers import make_row


def raw_frame(reference, rows):
    return pd.DataFrame([make_row(reference, **r) for r in rows])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_missing_required_columns_reported():
    missing, extra = validate_columns(pd.DataFrame({"Task_ID": ["1"]}))
    assert "Task" in missing
    assert "Department" in missing


def test_extra_columns_are_allowed():
    _, extra = validate_columns(
        pd.DataFrame({c: ["x"] for c in REQUIRED_COLUMNS + ["Surprise"]})
    )
    assert "Surprise" in extra


def valid_frame(rows: int = 1) -> pd.DataFrame:
    """A frame with the required schema, all cells as strings."""
    df = pd.DataFrame({c: ["x"] * rows for c in REQUIRED_COLUMNS})
    df["Task_ID"] = [f"A{i}" for i in range(rows)]
    df["Status"] = "In Progress"
    df["Priority"] = "Medium"
    df["Impact"] = "Low"
    df["Executive_Decision_Required"] = "No"
    df["Due_Date"] = "2026-01-01"
    df["Last_Updated"] = "2026-01-01"
    return df


def test_duplicate_task_ids_rejected():
    df = valid_frame(2)
    df["Task_ID"] = ["A", "A"]
    errors = validate_data(df)
    assert any("duplicate Task_ID" in e for e in errors)


def test_invalid_status_rejected():
    df = valid_frame(1)
    df["Status"] = "Waiting for Decision"
    errors = validate_data(df)
    assert any("Invalid Status" in e for e in errors)


def test_normalization_parses_dates_booleans_and_numbers(today):
    df = raw_frame(today, [{"Executive_Decision_Required": "Yes", "Impact_Value": "250000"}])
    out = normalize_data(df)
    assert out["Executive_Decision_Required"].iloc[0] is True or out["Executive_Decision_Required"].iloc[0] == True
    assert pd.notna(out["Due_Date"].iloc[0])
    assert float(out["Impact_Value"].iloc[0]) == 250000.0


def test_normalization_adds_optional_columns(today):
    df = raw_frame(today, [{}]).drop(columns=OPTIONAL_COLUMNS, errors="ignore")
    out = normalize_data(df)
    for col in OPTIONAL_COLUMNS:
        assert col in out.columns


def test_boolean_variants_accepted(today):
    df = raw_frame(today, [{"Executive_Decision_Required": "TRUE"}])
    out = normalize_data(df)
    assert bool(out["Executive_Decision_Required"].iloc[0]) is True


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

def test_column_aliases_are_suggested():
    uploaded = ["Task ID", "Title", "Team", "Assignee", "State", "Deadline", "Impact"]
    mapping, unmapped = suggest_column_mapping(uploaded)
    assert mapping["Task_ID"] == "Task ID"
    assert mapping["Task"] == "Title"
    assert mapping["Department"] == "Team"
    assert mapping["Owner"] == "Assignee"
    assert mapping["Status"] == "State"
    assert mapping["Due_Date"] == "Deadline"


def test_exact_schema_columns_match_first():
    mapping, _ = suggest_column_mapping(list(REQUIRED_COLUMNS))
    for col in REQUIRED_COLUMNS:
        assert mapping[col] == col


def test_unknown_values_detected():
    df = pd.DataFrame({"Status": ["Waiting for Decision", "In Progress"]})
    unknowns = find_unknown_values(df)
    assert "Waiting for Decision" in unknowns["Status"]
    assert "In Progress" not in unknowns["Status"]


def test_decision_flag_variants_need_no_mapping():
    """true/false/1/0 are valid decision flags, so they must not prompt."""
    df = pd.DataFrame({"Executive_Decision_Required": ["true", "False", "1", "0", "Yes", "No"]})
    assert find_unknown_values(df) == {}


def test_unknown_decision_flag_still_prompts():
    df = pd.DataFrame({"Executive_Decision_Required": ["Yes", "maybe"]})
    unknowns = find_unknown_values(df)
    assert "maybe" in unknowns["Executive_Decision_Required"]


def test_status_value_suggestions():
    suggestions = suggest_value_mapping({"Status": ["Waiting for Decision", "At Risk", "Complete"]})
    assert suggestions["Status"]["Waiting for Decision"] == "Blocked"
    assert suggestions["Status"]["Complete"] == "Done"


def test_apply_mapping_renames_and_translates():
    df = pd.DataFrame({"Task ID": ["A"], "State": ["Waiting for Decision"]})
    out = apply_mapping(df, {"Task_ID": "Task ID", "Status": "State"}, {"Status": {"Waiting for Decision": "Blocked"}})
    assert "Task_ID" in out.columns
    assert out["Status"].iloc[0] == "Blocked"


def test_apply_mapping_rejects_duplicate_source_column():
    df = pd.DataFrame({"A": ["1"], "B": ["2"]})
    with pytest.raises(DataValidationError):
        apply_mapping(df, {"Task_ID": "A", "Task": "A"}, {})


def test_mapped_frame_runs_the_full_pipeline(today):
    df = raw_frame(today, [{"Task_ID": "X", "Status": "Blocked", "Blocker": "vendor"}])
    out = process_mapped_frame(df)
    assert "attention_score" in out.columns
    assert int(out["blocked"].iloc[0]) == 1


def test_scope_keys_are_filesystem_safe():
    key = scope_key("gsheet:1BxiMVs0XRA5nFMd.../edit#gid=0")
    assert key.isidentifier()
    assert "/" not in key and " " not in key


def test_mapping_status_returns_full_shape(today):
    df = raw_frame(today, [{}])
    col_map, unmapped, unknowns, suggestions = mapping_status(df)
    assert set(col_map.keys()) >= set(REQUIRED_COLUMNS)
    assert isinstance(unmapped, list)
    assert isinstance(unknowns, dict)
    assert isinstance(suggestions, dict)


# ---------------------------------------------------------------------------
# End-to-end loading
# ---------------------------------------------------------------------------

def test_sample_csv_loads_and_validates():
    from tests.conftest import SAMPLE_CSV

    df = load_and_validate(file_path=SAMPLE_CSV)
    assert len(df) == 30
    assert df["Task_ID"].is_unique


def test_loader_rejects_unknown_format():
    with pytest.raises(DataValidationError):
        load_and_validate(file_path="data.txt")
