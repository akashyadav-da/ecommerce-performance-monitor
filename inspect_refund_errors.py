
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")

orders = pd.read_csv(RAW / "orders.csv")
items = pd.read_csv(RAW / "order_items.csv")
refunds = pd.read_csv(RAW / "refunds.csv")

items["line_gross"] = items["quantity"] * items["unit_price"]
items["line_net"] = items["line_gross"] - items["line_discount"]

totals = items.groupby("order_id", as_index=False).agg(
    gross_product_value=("line_gross", "sum"),
    line_discounts=("line_discount", "sum"),
    value_after_line_discounts=("line_net", "sum"),
)

audit = orders.merge(totals, on="order_id", how="left")
audit["value_after_all_discounts"] = (
    audit["value_after_line_discounts"] - audit["order_discount"]
)

refund_totals = refunds.groupby("order_id", as_index=False).agg(
    total_refunds=("refund_amount", "sum"),
    refund_count=("refund_id", "count"),
)

audit = audit.merge(refund_totals, on="order_id", how="left")
audit["total_refunds"] = audit["total_refunds"].fillna(0)
audit["refund_count"] = audit["refund_count"].fillna(0).astype(int)

exceptions = audit[
    (audit["status"] != "cancelled")
    & (audit["total_refunds"] > audit["value_after_all_discounts"] + 0.01)
].copy()

exceptions["excess_amount"] = (
    exceptions["total_refunds"] - exceptions["value_after_all_discounts"]
)

print("Exception count:", len(exceptions))
print("\nExcess refund by order:")
print(
    exceptions[[
        "order_id", "status", "gross_product_value",
        "line_discounts", "order_discount",
        "value_after_all_discounts", "total_refunds",
        "refund_count", "excess_amount"
    ]].head(15).round(2).to_string(index=False)
)

print("\nTotal excess across flagged orders:",
      round(exceptions["excess_amount"].sum(), 2))
