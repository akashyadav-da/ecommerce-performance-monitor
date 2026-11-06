
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")

orders = pd.read_csv(RAW / "orders.csv")
items = pd.read_csv(RAW / "order_items.csv")
refunds = pd.read_csv(RAW / "refunds.csv")

# Calculate each order's product value before discounts.
items["line_gross"] = items["quantity"] * items["unit_price"]

# Subtract line-level discounts.
items["line_net"] = items["line_gross"] - items["line_discount"]

order_totals = (
    items.groupby("order_id", as_index=False)
    .agg(
        gross_product_value=("line_gross", "sum"),
        line_discounts=("line_discount", "sum"),
        value_after_line_discounts=("line_net", "sum"),
        item_count=("product_id", "size"),
    )
)

audit = orders.merge(order_totals, on="order_id", how="left")

audit["value_after_all_discounts"] = (
    audit["value_after_line_discounts"] - audit["order_discount"]
)

# Calculate total refunds recorded against each order.
refund_totals = (
    refunds.groupby("order_id", as_index=False)
    .agg(total_refunds=("refund_amount", "sum"))
)

audit = audit.merge(refund_totals, on="order_id", how="left")
audit["total_refunds"] = audit["total_refunds"].fillna(0)

valid = audit[audit["status"] != "cancelled"].copy()

print("=== REVENUE VALIDATION ===")
print("Valid placed orders:", len(valid))
print("Valid orders missing item totals:", valid["item_count"].isna().sum())
print("Negative order discounts:",
      (audit["order_discount"] < 0).sum())
print("Discounts exceeding product value:",
      (audit["value_after_all_discounts"] < 0).sum())

print("\nOrders where refunds exceed value after discounts:",
      (valid["total_refunds"] > valid["value_after_all_discounts"] + 0.01).sum())

print("\nRefunds linked to cancelled orders:",
      refunds["order_id"].isin(
          orders.loc[orders["status"] == "cancelled", "order_id"]
      ).sum())

print("\nSummary for valid placed orders:")
print(valid[[
    "gross_product_value",
    "line_discounts",
    "order_discount",
    "value_after_all_discounts",
    "total_refunds",
]].sum().round(2).to_string())
