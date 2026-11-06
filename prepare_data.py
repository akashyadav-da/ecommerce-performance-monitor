
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Source files and their date columns
tables = {
    "orders": {
        "file": "orders.csv",
        "date_columns": ["order_date"],
    },
    "order_items": {
        "file": "order_items.csv",
        "date_columns": [],
    },
    "products": {
        "file": "products.csv",
        "date_columns": [],
    },
    "refunds": {
        "file": "refunds.csv",
        "date_columns": ["refund_date"],
    },
    "sessions": {
        "file": "sessions.csv",
        "date_columns": ["session_date"],
    },
}

print("Preparing validated data for Parquet storage...\n")

for table_name, config in tables.items():
    csv_path = RAW_DIR / config["file"]
    df = pd.read_csv(csv_path)

    # Convert date columns and reject invalid dates.
    for column in config["date_columns"]:
        df[column] = pd.to_datetime(df[column], errors="raise")

    parquet_path = PROCESSED_DIR / f"{table_name}.parquet"
    df.to_parquet(parquet_path, index=False)

    # Read the saved file back to verify it.
    check_df = pd.read_parquet(parquet_path)

    assert len(df) == len(check_df), f"Row count mismatch: {table_name}"

    for column in config["date_columns"]:
        assert pd.api.types.is_datetime64_any_dtype(
            check_df[column]
        ), f"Date conversion failed: {table_name}.{column}"

    print(
        f"{table_name}: {len(check_df):,} rows | "
        f"Saved: {parquet_path.name}"
    )

    for column in config["date_columns"]:
        print(
            f"  {column}: {check_df[column].dtype} | "
            f"{check_df[column].min().date()} to "
            f"{check_df[column].max().date()}"
        )

print("\nPreparation complete. All Parquet files verified.")
