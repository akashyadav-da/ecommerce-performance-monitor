
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ecommerce.duckdb"

con = duckdb.connect(str(DB_PATH), read_only=True)

print("=== TABLE ROW COUNTS ===")

tables = [
    "orders",
    "order_items",
    "products",
    "refunds",
    "sessions",
]

for table in tables:
    count = con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]
    print(f"{table}: {count:,}")

print("\n=== ORDER STATUS SUMMARY ===")

result = con.execute("""
    SELECT status, COUNT(*) AS order_count
    FROM orders
    GROUP BY status
    ORDER BY order_count DESC
""").df()

print(result.to_string(index=False))

con.close()
