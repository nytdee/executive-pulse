import sys
sys.path.insert(0, r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse')

from main import load_data

df = load_data('csv')
print(f'App loads successfully: {len(df)} rows')

attention = len(df[df["attention_score"] >= 4])
decisions = len(df[df["decision_required"] == True])
blocked = len(df[df["blocked"] == True])
at_risk = len(df[(df["at_risk"] == True) | (df["high_impact"] == True)])

print(f'Modules: Attention={attention}, Decisions={decisions}, Blocked={blocked}, AtRisk={at_risk}')
print('All imports successful!')