import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

import pandas as pd

from app.data.loader import REQUIRED_COLUMNS
from app.data.mapping import (
    apply_mapping,
    find_unknown_values,
    mapping_status,
    process_mapped_frame,
    scope_key,
    suggest_column_mapping,
    suggest_value_mapping,
)

# Frame mimicking real-world foreign sheets: odd headers, odd statuses,
# multi-value dependencies, non-padded times.
FOREIGN = pd.DataFrame([
    {
        "Task ID": "EP-001", "Title": "Approve budget", "Program": "Q4 Plan",
        "Dept": "Marketing", "Owner Name": "Priya", "State": "Waiting for Decision",
        "Prio": "Critical", "Deadline": "2026-09-29", "Severity": "Critical",
        "Business Impact": "450000", "Blocked By": "", "Depends On": "EP-006",
        "Updated": "2026-09-28 9:15", "Decision Needed": "Yes",
        "Decide By": "2026-09-29", "Approval": "Approve budget",
        "Link": "", "Comments": "Launch depends on approval.",
        "Owner Role": "Head", "Start": "2026-09-23",
    },
    {
        "Task ID": "EP-006", "Title": "Finance allocation", "Program": "Q4 Plan",
        "Dept": "Finance", "Owner Name": "Vikram", "State": "blocked",
        "Prio": "High", "Deadline": "2026-09-29", "Severity": "High",
        "Business Impact": "450000", "Blocked By": "CFO sign-off", "Depends On": "",
        "Updated": "2026-09-27 9:00", "Decision Needed": "No",
        "Decide By": "", "Approval": "",
        "Link": "", "Comments": "Feeds the decision.",
        "Owner Role": "Manager", "Start": "2026-09-24",
    },
    {
        "Task ID": "EP-030", "Title": "Operating plan", "Program": "Q4 Plan",
        "Dept": "Strategy", "Owner Name": "Aditya", "State": "In Progress",
        "Prio": "Critical", "Deadline": "2026-10-04", "Severity": "Critical",
        "Business Impact": "3500000", "Blocked By": "", "Depends On": "EP-001;EP-006",
        "Updated": "2026-09-28 11:15", "Decision Needed": "Yes",
        "Decide By": "2026-10-02", "Approval": "Approve assumptions",
        "Link": "", "Comments": "Depends on budget and forecast.",
        "Owner Role": "Lead", "Start": "2026-09-13",
    },
])

# 1. Alias suggestions cover every required column.
suggested, unmapped = suggest_column_mapping(list(FOREIGN.columns))
missing = [c for c in REQUIRED_COLUMNS if not suggested.get(c)]
assert not missing, f"unsuggested required columns: {missing}"
assert suggested["Task_ID"] == "Task ID", suggested
assert suggested["Status"] == "State", suggested
assert suggested["Due_Date"] == "Deadline", suggested
assert suggested["Executive_Decision_Required"] == "Decision Needed", suggested
print("1. column alias suggestions: OK")

# 2. Unknown detection: case-variant auto-accepted, foreign labels flagged.
renamed = FOREIGN.rename(columns={v: k for k, v in suggested.items() if v})
unknowns = find_unknown_values(renamed)
assert unknowns.get("Status") == ["Waiting for Decision"], unknowns
assert "Priority" not in unknowns and "Impact" not in unknowns, unknowns
print("2. unknown value detection (case-insensitive auto-match): OK")

# 3. Suggested status translations exist for the foreign labels.
suggestions = suggest_value_mapping(unknowns)
assert suggestions["Status"]["Waiting for Decision"] == "Blocked", suggestions
print("3. status translation suggestions: OK")

# 4. Full pipeline: apply suggested maps, validate, score.
columns = {k: v for k, v in suggested.items() if v}
values = {c: dict(s) for c, s in suggestions.items()}
mapped = apply_mapping(FOREIGN, columns, values)
df = process_mapped_frame(mapped)
assert len(df) == 3, len(df)
assert set(["attention_score", "score_band", "reason_codes"]) <= set(df.columns)
ep030 = df[df["Task_ID"] == "EP-030"].iloc[0]
assert bool(ep030["dependency_risk"]) is True, "multi-dependency risk missed"
assert "EP-006" in ep030["reason_codes"], ep030["reason_codes"]
print("4. end-to-end mapped pipeline + multi-dependency risk: OK")

# 5. Scope keys are stable and filesystem/session safe.
assert scope_key("gsheet:abc 123:0") == scope_key("gsheet:abc 123:0")
assert " " not in scope_key("a b/c?d")
print("5. scope keys: OK")

print("\nALL MAPPING TESTS PASSED!")
