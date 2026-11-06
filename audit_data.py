
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")

files = {
    "orders": "orders.csv",
    "order_items": "order_items.csv",
    "products": "products.csv",
    "refunds": "refunds.csv",
    "sessions": "sessions.csv",
}

for table, filename in files.items():
    df = pd.read_csv(RAW_DIR / filename)

    print(f"\n{'=' * 45}")
    print(f"TABLE: {table.upper()}")
    print(f"{'=' * 45}")

    print("Rows:", len(df))
    print("Columns:", len(df.columns))

    print("\nMissing values:")
    print(df.isna().sum().to_string())

    print("\nDuplicate rows:", df.duplicated().sum())

    print("\nData types:")
    print(df.dtypes.to_string())

    if table == "orders":
        print("\nOrder status counts:")
        print(df["status"].value_counts().to_string())

        print("\nOrder date range:")
        print(df["order_date"].min(), "to", df["order_date"].max())

    elif table == "order_items":
        print("\nNon-positive quantities:",
              (df["quantity"] <= 0).sum())
        print("Negative unit prices:",
              (df["unit_price"] < 0).sum())
        print("Negative line discounts:",
              (df["line_discount"] < 0).sum())

    elif table == "products":
        print("\nNon-positive unit costs:",
              (df["unit_cost"] <= 0).sum())
        print("Negative list prices:",
              (df["list_price"] < 0).sum())

    elif table == "refunds":
        print("\nNon-positive refund amounts:",
              (df["refund_amount"] <= 0).sum())
        print("Refund date range:")
        if not df.empty:
            print(df["refund_date"].min(), "to", df["refund_date"].max())
