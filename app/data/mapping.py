"""
Field-mapping layer for Executive Pulse.

Lets users attach sheets with arbitrary column names and value labels
(e.g. "Task ID" instead of "Task_ID", "Waiting for Decision" instead of
"Blocked") and map them onto the canonical schema before the existing
validation + rule-engine pipeline runs.

Nothing here changes scoring, ranking or validation rules — it only
translates foreign labels into canonical ones.
"""

from __future__ import annotations

import re

import pandas as pd

from app.data.loader import (
    ALL_COLUMNS,
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    VALID_STATUSES,
    VALID_PRIORITIES,
    VALID_IMPACTS,
    VALID_DECISION_VALUES,
    DataValidationError,
    normalize_data,
    validate_columns,
    validate_data,
)
from app.engine.rule_engine import compute_all_flags, rank_attention


def normalize_header(name: str) -> str:
    """Canonical key for fuzzy header matching: lower, alnum only."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def scope_key(source_key: str) -> str:
    """Stable session-state namespace for one attached source."""
    return re.sub(r"[^A-Za-z0-9_]", "_", source_key or "src")[:60]


# Canonical-key → schema column. Covers common real-world variants.
COLUMN_ALIASES = {
    "taskid": "Task_ID", "taskno": "Task_ID", "id": "Task_ID", "key": "Task_ID",
    "task": "Task", "taskname": "Task", "title": "Task", "workitem": "Task",
    "name": "Task", "summary": "Task", "subject": "Task",
    "project": "Project", "program": "Project", "initiative": "Project",
    "epic": "Project", "campaign": "Project", "workstream": "Project",
    "department": "Department", "dept": "Department", "team": "Department",
    "function": "Department",
    "owner": "Owner", "ownername": "Owner", "assignee": "Owner",
    "responsible": "Owner", "lead": "Owner", "accountable": "Owner",
    "ownerrole": "Owner_Role", "role": "Owner_Role", "ownerfunction": "Owner_Role",
    "title_role": "Owner_Role",
    "status": "Status", "state": "Status", "stage": "Status",
    "priority": "Priority", "prio": "Priority", "urgency": "Priority",
    "startdate": "Start_Date", "start": "Start_Date", "startdated": "Start_Date",
    "duedate": "Due_Date", "due": "Due_Date", "deadline": "Due_Date",
    "targetdate": "Due_Date", "enddate": "Due_Date",
    "completeddate": "Completed_Date", "donedate": "Completed_Date",
    "completed": "Completed_Date", "closedate": "Completed_Date",
    "finishdate": "Completed_Date",
    "impact": "Impact", "severity": "Impact", "criticality": "Impact",
    "impactvalue": "Impact_Value", "businessimpact": "Impact_Value",
    "value": "Impact_Value", "arr": "Impact_Value", "revenueatrisk": "Impact_Value",
    "amount": "Impact_Value",
    "blocker": "Blocker", "blockers": "Blocker", "blockedby": "Blocker",
    "blockingreason": "Blocker", "impediment": "Blocker", "blockreason": "Blocker",
    "dependency": "Dependency", "dependencies": "Dependency",
    "dependson": "Dependency", "depends": "Dependency", "relieson": "Dependency",
    "blockedtask": "Dependency",
    "blockerowner": "Blocker_Owner", "unblockowner": "Blocker_Owner",
    "waitingon": "Blocker_Owner", "blockedowner": "Blocker_Owner",
    "lastupdated": "Last_Updated", "updated": "Last_Updated",
    "lastupdate": "Last_Updated", "modified": "Last_Updated",
    "lastmodified": "Last_Updated", "updatedat": "Last_Updated",
    "executivedecisionrequired": "Executive_Decision_Required",
    "decisionrequired": "Executive_Decision_Required",
    "needsexecdecision": "Executive_Decision_Required",
    "execdecision": "Executive_Decision_Required",
    "requiresdecision": "Executive_Decision_Required",
    "decisionneeded": "Executive_Decision_Required",
    "decisionby": "Decision_By", "decideby": "Decision_By",
    "decisiondate": "Decision_By", "decisiondeadline": "Decision_By",
    "neededby": "Decision_By",
    "decisionrequested": "Decision_Requested",
    "decision": "Decision_Requested",
    "approvalneeded": "Decision_Requested",
    "sourceurl": "Source_URL", "link": "Source_URL", "url": "Source_URL",
    "sourcelink": "Source_URL", "ticket": "Source_URL", "jira": "Source_URL",
    "notes": "Notes", "note": "Notes", "comments": "Notes",
    "comment": "Notes", "description": "Notes", "details": "Notes",
    "context": "Notes", "remarks": "Notes",
}

# Suggested canonical status for common foreign labels (user can override).
STATUS_SUGGESTIONS = {
    "waiting for decision": "Blocked",
    "awaiting decision": "Blocked",
    "pending approval": "Blocked",
    "awaiting approval": "Blocked",
    "at risk": "In Progress",
    "atrisk": "In Progress",
    "stale": "In Progress",
    "on track": "In Progress",
    "todo": "Not Started",
    "to do": "Not Started",
    "backlog": "Not Started",
    "complete": "Done",
    "completed": "Done",
    "closed": "Done",
    "cancelled": "On Hold",
    "paused": "On Hold",
}

VALUE_COLUMNS = {
    "Status": sorted(VALID_STATUSES),
    "Priority": sorted(VALID_PRIORITIES),
    "Impact": sorted(VALID_IMPACTS),
    "Executive_Decision_Required": ["Yes", "No"],
}


def suggest_column_mapping(uploaded_columns: list) -> tuple:
    """Suggest schema←uploaded mapping. Returns (mapping, unmapped)."""
    mapping: dict = {}
    used = set()
    by_key: dict = {}
    for col in uploaded_columns:
        by_key.setdefault(normalize_header(col), []).append(col)

    for schema_col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if schema_col in uploaded_columns and schema_col not in used:
            mapping[schema_col] = schema_col
            used.add(schema_col)
            continue
        candidates = [
            col for key, cols in by_key.items()
            for col in cols
            if COLUMN_ALIASES.get(key) == schema_col and col not in used
        ]
        if candidates:
            mapping[schema_col] = candidates[0]
            used.add(candidates[0])

    # Required columns without a suggestion get None (user must choose).
    for schema_col in REQUIRED_COLUMNS:
        mapping.setdefault(schema_col, None)

    unmapped = [c for c in uploaded_columns if c not in used]
    return mapping, unmapped


def _canonical_lookup(valid_values) -> dict:
    return {str(v).strip().lower(): v for v in valid_values}


def find_unknown_values(df: pd.DataFrame) -> dict:
    """Unknown labels needing user mapping, after case-insensitive auto-match."""
    unknowns: dict = {}
    for col, valid in VALUE_COLUMNS.items():
        if col not in df.columns:
            continue
        canonical = _canonical_lookup(valid)
        series = df[col].astype(str).str.strip()
        series = series[~series.isin(["", "nan", "None", "NaT"])]
        unknown = sorted({v for v in series.unique() if str(v).strip().lower() not in canonical})
        if unknown:
            unknowns[col] = unknown
    return unknowns


def suggest_value_mapping(unknowns: dict) -> dict:
    """Prefill suggestions; user can override every one."""
    suggestions: dict = {}
    for col, values in unknowns.items():
        col_suggestions = {}
        for value in values:
            if col == "Status":
                col_suggestions[value] = STATUS_SUGGESTIONS.get(value.strip().lower(), "In Progress")
            elif col == "Executive_Decision_Required":
                lowered = value.strip().lower()
                col_suggestions[value] = "Yes" if lowered in ("yes", "y", "true", "1") else "No"
            else:
                col_suggestions[value] = VALUE_COLUMNS[col][0]
        suggestions[col] = col_suggestions
    return suggestions


def apply_mapping(df: pd.DataFrame, column_mapping: dict, value_mapping: dict) -> pd.DataFrame:
    """Rename columns and translate labels. Raises DataValidationError on conflicts."""
    # Detect two uploaded columns mapped to the same schema column.
    seen: dict = {}
    for schema_col, uploaded_col in column_mapping.items():
        if not uploaded_col:
            continue
        if uploaded_col in seen:
            raise DataValidationError(
                f"Columns '{seen[uploaded_col]}' and '{schema_col}' both map from "
                f"'{uploaded_col}'. Each sheet column can map to one field only."
            )
        seen[uploaded_col] = schema_col

    result = df.rename(columns={v: k for k, v in column_mapping.items() if v}).copy()

    # Case-insensitive auto-normalization for known labels.
    for col, valid in VALUE_COLUMNS.items():
        if col not in result.columns:
            continue
        canonical = _canonical_lookup(valid)
        mask = result[col].notna()
        result.loc[mask, col] = result.loc[mask, col].astype(str).str.strip()
        lowered = result.loc[mask, col].str.lower()
        auto = lowered.map(canonical)
        result.loc[mask, col] = auto.fillna(result.loc[mask, col])

    # User-directed translations.
    for col, translations in (value_mapping or {}).items():
        if col in result.columns and translations:
            result[col] = result[col].replace(translations)

    return result


def process_mapped_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate + normalize + score a mapped frame through the standard pipeline."""
    missing, _extra = validate_columns(df)
    if missing:
        raise DataValidationError(f"Missing required columns after mapping: {missing}")
    errors = validate_data(df)
    if errors:
        raise DataValidationError("; ".join(errors))
    normalized = normalize_data(df)
    scored = compute_all_flags(normalized)
    return rank_attention(scored)


def mapping_status(raw_df: pd.DataFrame) -> tuple:
    """Inspect a raw frame. Returns (column_mapping, unmapped, unknowns, suggestions)."""
    column_mapping, unmapped = suggest_column_mapping(list(raw_df.columns))
    renamed = raw_df.rename(columns={v: k for k, v in column_mapping.items() if v})
    unknowns = find_unknown_values(renamed)
    suggestions = suggest_value_mapping(unknowns)
    return column_mapping, unmapped, unknowns, suggestions
