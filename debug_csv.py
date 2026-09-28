import pandas as pd

df = pd.read_csv(
    r'C:\Users\deepa\Downloads\CXO Offer\executive_pulse\app\data\sample_data.csv',
    dtype=str,
    keep_default_na=False,
    na_filter=False,
)

print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"Number of columns: {len(df.columns)}")

# Check each row's non-null count
for idx, row in df.iterrows():
    non_null = row[row != ''].count()
    if non_null < 21:
        print(f"Row {idx} (Task_ID={row.get('Task_ID', 'N/A')}): {non_null} non-null fields")
        print(f"  Values: {row.tolist()}")

# Check specific columns
print("\nExecutive_Decision_Required values:")
print(df['Executive_Decision_Required'].value_counts())

print("\nLast_Updated values (first 10):")
print(df['Last_Updated'].head(10).tolist())

print("\nDecision_By values (first 10):")
print(df['Decision_By'].head(10).tolist())