
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")

date_columns = {
    "orders.csv": ["order_date"],
    "refunds.csv": ["refund_date"],
    "sessions.csv": ["session_date"],
}

for filename, columns in date_columns.items():
    df = pd.read_csv(RAW_DIR / filename)

    print(f"\n--- {filename} ---")

    for column in columns:
        original = df[column]
        converted = pd.to_datetime(original, errors="coerce")

        invalid_count = converted.isna().sum()
        print(f"{column}:")
        print("  Invalid or missing dates:", invalid_count)

        if converted.notna().any():
            print("  Minimum:", converted.min())
            print("  Maximum:", converted.max())

        if invalid_count == 0:
            df[column] = converted
            print("  Conversion successful")
        else:
            print("  Conversion needs investigation")

    if all(pd.to_datetime(df[c], errors="coerce").notna().all()
           for c in columns):
        df.to_csv(RAW_DIR / filename, index=False)

print("\nDate validation finished.")
