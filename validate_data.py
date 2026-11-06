
from pathlib import Path
import sys
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"

ERRORS = []


def add_error(message):
    ERRORS.append(message)
    print(f"[FAIL] {message}")


def main():
    print("=== RAW DATA VALIDATION ===\n")

    # 1. Load source files
    try:
        orders = pd.read_csv(RAW_DIR / "orders.csv")
        items = pd.read_csv(RAW_DIR / "order_items.csv")
        products = pd.read_csv(RAW_DIR / "products.csv")
        refunds = pd.read_csv(RAW_DIR / "refunds.csv")
    except Exception as error:
        add_error(f"Could not load raw data: {error}")
        return 1

    # 2. Check required columns
    required_columns = {
        "orders": (orders, ["order_id", "status", "order_date"]),
        "order_items": (items, ["order_id", "product_id", "quantity", "unit_price"]),
        "products": (products, ["product_id"]),
        "refunds": (refunds, ["order_id", "product_id", "refund_amount"]),
    }

    for table_name, (df, columns) in required_columns.items():
        missing = [column for column in columns if column not in df.columns]
        if missing:
            add_error(f"{table_name} missing columns: {missing}")

    if ERRORS:
        return 1

    # 3. Check duplicate primary IDs
    if orders["order_id"].duplicated().any():
        add_error("Duplicate order IDs found.")

    if products["product_id"].duplicated().any():
        add_error("Duplicate product IDs found.")

    # 4. Check relationships
    unknown_order_items = ~items["order_id"].isin(orders["order_id"])
    if unknown_order_items.any():
        add_error(
            f"{unknown_order_items.sum()} order items reference unknown orders."
        )

    unknown_item_products = ~items["product_id"].isin(products["product_id"])
    if unknown_item_products.any():
        add_error(
            f"{unknown_item_products.sum()} order items reference unknown products."
        )

    unknown_refund_orders = ~refunds["order_id"].isin(orders["order_id"])
    if unknown_refund_orders.any():
        add_error(
            f"{unknown_refund_orders.sum()} refunds reference unknown orders."
        )

    unknown_refund_products = ~refunds["product_id"].isin(products["product_id"])
    if unknown_refund_products.any():
        add_error(
            f"{unknown_refund_products.sum()} refunds reference unknown products."
        )

    # 5. Every non-cancelled order must have order items
    valid_orders = orders.loc[orders["status"] != "cancelled", "order_id"]
    orders_without_items = ~valid_orders.isin(items["order_id"])

    if orders_without_items.any():
        add_error(
            f"{orders_without_items.sum()} valid orders have no order items."
        )

    # 6. Final result
    print("\n=== VALIDATION SUMMARY ===")

    if ERRORS:
        print(f"VALIDATION FAILED: {len(ERRORS)} error(s) found.")
        return 1

    print("VALIDATION PASSED.")
    print(f"Orders: {len(orders):,}")
    print(f"Order items: {len(items):,}")
    print(f"Products: {len(products):,}")
    print(f"Refunds: {len(refunds):,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
