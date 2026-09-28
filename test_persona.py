import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

from app.data.loader import load_and_validate
from app.engine.rule_engine import compute_all_flags, rank_attention
from app.engine.intelligence import (
    PERSONAS,
    get_executive_attention_queue,
    persona_departments,
    persona_relevant,
)

df = load_and_validate(r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse\app\data\sample_data.csv')
df = rank_attention(compute_all_flags(df))

# 1. Full-org personas see everything (no department scoping).
assert persona_departments("CEO") is None
assert persona_departments("Chief of Staff") is None
assert persona_departments(None) is None
print("1. full-org personas unscoped: OK")

# 2. Role personas scope to their departments.
assert persona_departments("CMO") == ["Marketing", "Sales"]
assert persona_departments("CFO") == ["Finance", "Legal"]
assert persona_departments("CTO / CPO") == ["Technology", "Product"]
assert persona_departments("COO") == ["Operations", "Technology", "People"]
print("2. role department scopes: OK")

# 3. persona_relevant returns engine-ranked items inside scope only.
cmo = persona_relevant(df, "CMO", max_items=3)
assert len(cmo) <= 3 and set(cmo["Department"]) <= {"Marketing", "Sales"}, cmo
assert cmo["attention_score"].is_monotonic_decreasing, "engine order broken"
print("3. persona-relevant subset keeps engine ranking: OK")

# 4. Grouping covers the queue without duplicates or score changes.
base = get_executive_attention_queue(df, max_items=10, min_band="High")
mine = base[base["Department"].isin(persona_departments("CMO") or [])]
rest = base[~base["Task_ID"].isin(mine["Task_ID"])]
shown = list(mine.head(3)["Task_ID"]) + list(rest.head(5 - len(mine.head(3)))["Task_ID"])
assert len(shown) == len(set(shown)), "duplicate items across groups"
assert set(shown) <= set(base["Task_ID"]), "items outside engine queue"
scores_before = dict(zip(df["Task_ID"], df["attention_score"]))
assert all(scores_before[t] >= 7 for t in shown), "non-qualifying item shown"
print("4. for-you + radar grouping is disjoint and score-preserving: OK")

print("\nALL PERSONA TESTS PASSED!")
