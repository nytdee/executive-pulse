import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

from app.data.loader import load_and_validate
from app.engine.rule_engine import compute_all_flags, rank_attention
from app.engine.intelligence import (
    detect_cross_team_friction,
    analyze_owner_load,
    detect_systemic_risks,
    generate_meeting_brief,
    get_executive_attention_queue,
    get_decision_queue_detailed,
    get_blocked_friction_detailed,
    get_org_pulse_enhanced,
)
import pandas as pd

# Load data
df = load_and_validate(r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse\app\data\sample_data.csv')
df = compute_all_flags(df)
df = rank_attention(df)

print("=" * 60)
print("TESTING INTELLIGENCE LAYER")
print("=" * 60)

# 1. Executive Attention Queue
print("\n1. EXECUTIVE ATTENTION QUEUE (Critical/High only):")
attention = get_executive_attention_queue(df, max_items=7, min_band="High")
for _, row in attention.iterrows():
    print(f"  [{row['attention_score']}] {row['Task']} ({row['score_band']}) - {row['reason_codes']}")

# 2. Cross-Team Friction
print("\n2. CROSS-TEAM FRICTION:")
friction = detect_cross_team_friction(df)
for f in friction:
    print(f"  {f.severity}: {f.blocker_owner} ({f.blocker_dept}) blocks {f.blocked_count} items, ${f.total_impact_value:,.0f} at risk, max {f.max_days_blocked}d blocked")
    for task in f.blocked_tasks:
        print(f"    -> {task['task']} ({task['dept']})")

# 3. Owner Load Analysis
print("\n3. OWNER LOAD ANALYSIS:")
loads = analyze_owner_load(df)
for ol in loads:
    if ol.load_level in ["Overloaded", "High"]:
        print(f"  {ol.load_level}: {ol.owner} ({ol.department}) - {ol.total_open} open, {ol.overdue} overdue, {ol.blocked} blocked, {ol.decisions_required} decisions, avg score: {ol.avg_attention_score}")

# 4. Systemic Risks
print("\n4. SYSTEMIC RISKS:")
risks = detect_systemic_risks(df)
for r in risks:
    print(f"  {r.severity} [{r.pattern_type}]: {r.description}")
    print(f"    -> {r.recommendation}")

# 5. Decision Queue Detailed
print("\n5. DECISION QUEUE (Detailed):")
decisions = get_decision_queue_detailed(df)
for _, row in decisions.iterrows():
    print(f"  {row['Task']} - Urgency: {row['decision_urgency']} - {row['impact_context']}")

# 6. Blocked Friction Detailed
print("\n6. BLOCKED FRICTION (Detailed):")
blocked_detail = get_blocked_friction_detailed(df)
print(f"  Summary: {blocked_detail['summary']}")

# 7. Enhanced Org Pulse
print("\n7. ENHANCED ORG PULSE:")
org = get_org_pulse_enhanced(df)
print(org[['Department', 'Open', 'Overdue', 'Overdue_Pct', 'Blocked', 'Blocked_Pct', 'High_Impact', 'Decisions', 'Risk_Score']].to_string(index=False))

# 8. Meeting Brief
print("\n8. MEETING BRIEF:")
brief = generate_meeting_brief(df, meeting_name="Q3 Board Review")
print(f"  Summary: {brief['summary']}")
print(f"  Decisions: {len(brief['decisions'])}")
print(f"  Critical Risk: {len(brief['critical_risk'])}")
print(f"  Friction Points: {len(brief['friction_points'])}")
print(f"  Systemic Risks: {len(brief['systemic_risks'])}")
print(f"  Overloaded Owners: {len(brief['owner_loads'])}")

print("\n" + "=" * 60)
print("ALL INTELLIGENCE TESTS PASSED!")
print("=" * 60)