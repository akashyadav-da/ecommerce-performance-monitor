
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
DB_PATH = BASE_DIR / "ecommerce.duckdb"

con = duckdb.connect(str(DB_PATH))

tables = [
    "orders",
    "order_items",
    "products",
    "refunds",
    "sessions",
]

for table in tables:
    parquet_path = (DATA_DIR / f"{table}.parquet").as_posix()

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT * FROM read_parquet('{parquet_path}')
    """)

    row_count = con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    print(f"{table}: {row_count:,} rows loaded")

print("\nDuckDB setup complete.")

con.close()
