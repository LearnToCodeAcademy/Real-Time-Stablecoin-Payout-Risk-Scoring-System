import os
import pandas as pd

ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT, "datasets")
MODEL_DIR = os.path.join(ROOT, "models")

print("Dataset report:")
if not os.path.exists(DATA_DIR):
    print("  datasets/ directory not found.")
else:
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
    if not files:
        print("  no csv files found in datasets/")
    for f in files:
        path = os.path.join(DATA_DIR, f)
        try:
            # fast row count without loading full file
            with open(path, 'rb') as fh:
                row_count = sum(1 for _ in fh) - 1
        except Exception:
            row_count = 'unknown'
        print(f"  - {f}: {row_count} rows")

print('\nModel artifacts:')
if not os.path.exists(MODEL_DIR):
    print('  models/ directory not found.')
else:
    mfiles = sorted([f for f in os.listdir(MODEL_DIR) if f.endswith('.pkl')])
    if not mfiles:
        print('  no model files found in models/')
    for mf in mfiles:
        print(f"  - {mf}")

print('\nQuick checks complete.')
