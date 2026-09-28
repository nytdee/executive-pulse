import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

import pandas as pd

from app.data.loader import load_and_validate
from app.engine.rule_engine import compute_all_flags, rank_attention
from app.engine.intelligence import (
    extract_profile_keywords,
    get_executive_attention_queue,
    profile_relevance,
)

# 1. Extraction keeps substance, drops filler.
keywords = extract_profile_keywords(
    "I am the chief brand officer and my priorities include brand launches, partnerships, customer escalations"
)
for expected in ["brand", "launches", "partnerships", "customer", "escalations"]:
    assert expected in keywords, keywords
for filler in ["i", "am", "my", "and", "include", "the"]:
    assert filler not in keywords, keywords
assert extract_profile_keywords("   ") == []
assert extract_profile_keywords(None) == []
assert extract_profile_keywords("and the for me") == []
print("1. keyword extraction: OK")

# 2. Prefix-tolerant matching: launch hits launches, brand hits branding.
row = pd.Series({
    "Task": "Festive campaign launches", "Project": "Growth", "Department": "Marketing",
    "Owner": "Rohan", "Owner_Role": "Manager", "Blocker": "",
    "Notes": "Rebranding review pending.", "Decision_Requested": "",
})
score, matched = profile_relevance(row, ["launch", "brand", "crm"])
assert score > 0 and set(matched) == {"launch", "brand"}, (score, matched)
score_none, matched_none = profile_relevance(row, ["crm"])
assert (score_none, matched_none) == (0, [])
print("2. prefix-tolerant matching + no-match fallback: OK")

# 3. Title hits outrank notes-only hits.
title_row = pd.Series({c: "" for c in
    ["Task", "Project", "Department", "Owner", "Owner_Role", "Blocker", "Notes", "Decision_Requested"]})
title_row["Task"] = "Brand film approval"
notes_row = title_row.copy()
notes_row["Task"] = "Routine reconciliation"
notes_row["Notes"] = "Brand assets attached."
assert profile_relevance(title_row, ["brand"])[0] > profile_relevance(notes_row, ["brand"])[0]
print("3. title-weighted relevance: OK")

# 4. End to end on sample data: matches stay inside the engine queue,
#    engine order preserved, scores untouched.
df = load_and_validate(r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse\app\data\sample_data.csv')
df = rank_attention(compute_all_flags(df))
keywords = extract_profile_keywords("brand launches, partnerships, customer escalations")
queue = get_executive_attention_queue(df, max_items=10, min_band="High")
assert not queue.empty
hits = []
for _, r in queue.iterrows():
    relevance, matched = profile_relevance(r, keywords)
    if relevance > 0:
        hits.append((r["Task_ID"], matched))
assert hits, "expected at least one profile match in sample data"
before = dict(zip(df["Task_ID"], df["attention_score"]))
assert all(before[tid] >= 7 for tid, _ in hits)
queue_scores = [before[tid] for tid in queue["Task_ID"]]
assert queue_scores == sorted(queue_scores, reverse=True), "engine order broken"
print(f"4. sample-data profile grouping ({len(hits)} matches): OK")

print("\nALL PROFILE TESTS PASSED!")
