
from pathlib import Path
import random
import pandas as pd

# Reproducible data: the same seed produces the same dataset.
random.seed(42)
rng = random.Random(42)

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# 1. Products
# -----------------------------
categories = {
    "Electronics": ["Headphones", "Keyboard", "Mouse", "Speaker", "Monitor"],
    "Home": ["Lamp", "Bottle", "Storage Box", "Bedsheet", "Cushion"],
    "Fashion": ["T-shirt", "Jeans", "Shoes", "Backpack", "Cap"],
    "Beauty": ["Face Wash", "Moisturizer", "Shampoo", "Sunscreen", "Serum"],
    "Sports": ["Yoga Mat", "Dumbbells", "Skipping Rope", "Sports Bottle", "Tennis Racket"],
}

products = []
product_id = 1

for category, names in categories.items():
    for name in names:
        price = rng.choice([299, 499, 799, 999, 1499, 1999, 2999, 4999])
        products.append({
            "product_id": f"P{product_id:03}",
            "product_name": name,
            "category": category,
            "unit_cost": round(price * rng.uniform(0.45, 0.75), 2),
            "list_price": price,
        })
        product_id += 1

products_df = pd.DataFrame(products)
products_df.to_csv(RAW_DIR / "products.csv", index=False)

# -----------------------------
# 2. Orders and order items
# -----------------------------
start_date = pd.Timestamp("2025-10-01")
end_date = pd.Timestamp("2026-10-31")
n_orders = 10_000

channels = ["Google Search", "Instagram Ads", "Email", "Direct", "Referral"]
regions = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Pune", "Chennai"]
statuses = ["processing", "shipped", "delivered", "cancelled"]

orders = []
items = []
sessions = []
refunds = []

for i in range(1, n_orders + 1):
    order_id = f"O{i:06}"
    order_date = start_date + pd.Timedelta(
        days=rng.randint(0, (end_date - start_date).days)
    )
    customer_id = f"C{rng.randint(1, 6500):05}"
    status = rng.choices(statuses, weights=[8, 12, 75, 5])[0]
    channel = rng.choices(channels, weights=[30, 25, 20, 15, 10])[0]
    region = rng.choice(regions)

    # Each order contains 1–4 product lines.
    n_lines = rng.randint(1, 4)
    order_product_ids = rng.sample(
        list(products_df["product_id"]), n_lines
    )

    order_items = []
    pre_discount_total = 0

    for pid in order_product_ids:
        product = products_df.loc[
            products_df["product_id"] == pid
        ].iloc[0]

        quantity = rng.randint(1, 3)
        unit_price = int(product["list_price"])
        line_discount = round(
            unit_price * quantity * rng.choice([0, 0.05, 0.10, 0.15]), 2
        )

        line_gross = unit_price * quantity
        pre_discount_total += line_gross

        order_items.append({
            "order_id": order_id,
            "product_id": pid,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_discount": line_discount,
        })

    # Order-level discount is separate from line discounts.
    order_discount = round(
        max(0, pre_discount_total - sum(x["line_discount"] for x in order_items))
        * rng.choice([0, 0, 0.03, 0.05]), 2
    )

    orders.append({
        "order_id": order_id,
        "customer_id": customer_id,
        "order_date": order_date.strftime("%Y-%m-%d"),
        "status": status,
        "order_discount": order_discount,
        "channel": channel,
        "region": region,
    })
    items.extend(order_items)

    # One attributed session per order, plus non-converting sessions.
    sessions.append({
        "session_id": f"S{i:07}",
        "session_date": order_date.strftime("%Y-%m-%d"),
        "channel": channel,
        "region": region,
        "converted_order_id": order_id,
    })

    for extra in range(rng.randint(1, 4)):
        session_date = order_date - pd.Timedelta(days=rng.randint(0, 14))
        sessions.append({
            "session_id": f"S{i:07}X{extra}",
            "session_date": session_date.strftime("%Y-%m-%d"),
            "channel": channel,
            "region": region,
            "converted_order_id": None,
        })

    
    # Refunds are recorded on their issue date, not the order date.
    if status != "cancelled" and rng.random() < 0.08:
        item = rng.choice(order_items)

        # Allocate the order-level discount proportionally to this product line.
        line_gross = item["quantity"] * item["unit_price"]
        total_line_gross = sum(
            x["quantity"] * x["unit_price"] for x in order_items
        )

        allocated_order_discount = (
            order_discount * line_gross / total_line_gross
            if total_line_gross > 0 else 0
        )

        # Calculate the maximum refundable amount after both discounts.
        refundable = max(
            0,
            line_gross
            - item["line_discount"]
            - allocated_order_discount
        )

        refund_amount = round(
            refundable * rng.choice([0.25, 0.5, 1.0]), 2
        )

        refund_date = order_date + pd.Timedelta(days=rng.randint(1, 45))

        refunds.append({
            "refund_id": f"R{len(refunds) + 1:06}",
            "order_id": order_id,
            "product_id": item["product_id"],
            "refund_date": refund_date.strftime("%Y-%m-%d"),
            "refund_amount": refund_amount,
        })


orders_df = pd.DataFrame(orders)
items_df = pd.DataFrame(items)
refunds_df = pd.DataFrame(refunds)
sessions_df = pd.DataFrame(sessions)

# Save raw source files.
orders_df.to_csv(RAW_DIR / "orders.csv", index=False)
items_df.to_csv(RAW_DIR / "order_items.csv", index=False)
refunds_df.to_csv(RAW_DIR / "refunds.csv", index=False)
sessions_df.to_csv(RAW_DIR / "sessions.csv", index=False)

print("Dataset generation complete.")
for filename, df in {
    "products.csv": products_df,
    "orders.csv": orders_df,
    "order_items.csv": items_df,
    "refunds.csv": refunds_df,
    "sessions.csv": sessions_df,
}.items():
    print(f"{filename}: {len(df):,} rows")
