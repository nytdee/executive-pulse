import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

from app.data.loader import load_and_validate
from app.engine.rule_engine import compute_all_flags, rank_attention, get_attention_queue, get_decision_queue, get_at_risk, get_blocked_items, get_stale_work, get_org_pulse
import pandas as pd

# Test data loading
df = load_and_validate(r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse\app\data\sample_data.csv')
print(f'Loaded {len(df)} rows')
print(f'Columns: {list(df.columns)}')

# Test rule engine
df = compute_all_flags(df)
df = rank_attention(df)
print(f'After rule engine: {len(df)} rows')
print(f'Score bands: {df["score_band"].value_counts().to_dict()}')
print(f'Scores: {df["attention_score"].min()} - {df["attention_score"].max()}')

# Show top attention items
top = df.head(7)
for _, row in top.iterrows():
    print(f'  [{row["attention_score"]}] {row["Task"]} ({row["score_band"]}) - {row["reason_codes"]}')

# Test module functions
attention = get_attention_queue(df)
print(f'\nAttention queue: {len(attention)} items')

decisions = get_decision_queue(df)
print(f'Decision queue: {len(decisions)} items')

at_risk = get_at_risk(df)
print(f'At risk: {len(at_risk)} items')

blocked = get_blocked_items(df)
print(f'Blocked: {len(blocked)} items')

stale = get_stale_work(df)
print(f'Stale: {len(stale)} items')

org = get_org_pulse(df)
print(f'Org pulse: {len(org)} departments')
print(org[['Department', 'Open', 'Overdue', 'Blocked', 'High_Impact', 'Decision_Required']].to_string(index=False))

print('\nAll tests passed!')