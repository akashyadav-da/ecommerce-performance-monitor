
from pathlib import Path
import pandas as pd
import duckdb

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "ecommerce.duckdb"

TABLE_CONFIG = {
    "orders": {
        "file": "orders.csv",
        "keys": ["order_id"],
        "dates": ["order_date"]
    },
    "order_items": {
        "file": "order_items.csv",
        "keys": ["order_id", "product_id"],
        "dates": []
    },
    "products": {
        "file": "products.csv",
        "keys": ["product_id"],
        "dates": []
    },
    "refunds": {
        "file": "refunds.csv",
        "keys": ["refund_id"],
        "dates": ["refund_date"]
    },
    "sessions": {
        "file": "sessions.csv",
        "keys": ["session_id"],
        "dates": ["session_date"]
    }
}


def load_and_stage(con, table, config):
    file_path = RAW_DIR / config["file"]

    if not file_path.exists():
        raise FileNotFoundError(f"Missing file: {file_path}")

    df = pd.read_csv(file_path)

    # Confirm source columns match the target table.
    target_columns = [
        row[0] for row in con.execute(
            f"DESCRIBE {table}"
        ).fetchall()
    ]

    if set(df.columns) != set(target_columns):
        raise ValueError(
            f"{table}: source and target columns do not match"
        )

    # Keep source columns in the target table's order.
    df = df[target_columns]

    # Convert date columns explicitly.
    for col in config["dates"]:
        original = df[col].copy()
        df[col] = pd.to_datetime(df[col], errors="coerce")

        invalid = original.notna() & df[col].isna()

        if invalid.any():
            raise ValueError(
                f"{table}: invalid dates found in {col}"
            )

    # Validate merge keys.
    keys = config["keys"]

    if df[keys].isnull().any().any():
        raise ValueError(
            f"{table}: missing values in merge keys"
        )

    if df.duplicated(subset=keys).any():
        raise ValueError(
            f"{table}: duplicate merge keys found"
        )

    # Create temporary staging table.
    source_name = f"source_{table}"
    staging_name = f"staging_{table}"

    con.register(source_name, df)

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE {staging_name} AS
        SELECT * FROM {source_name}
    """)

    con.unregister(source_name)

    staged_count = con.execute(
        f"SELECT COUNT(*) FROM {staging_name}"
    ).fetchone()[0]

    print(f"[PASS] {table}: {staged_count:,} rows staged")


def merge_table(con, table, config):
    keys = config["keys"]

    target_columns = [
        row[0] for row in con.execute(
            f"DESCRIBE {table}"
        ).fetchall()
    ]

    non_key_columns = [
        col for col in target_columns if col not in keys
    ]

    source = f"staging_{table}"

    # Match source records with existing target records.
    join_condition = " AND ".join(
        f"t.{key} = s.{key}" for key in keys
    )

    matched_count = con.execute(f"""
        SELECT COUNT(*)
        FROM {source} s
        INNER JOIN {table} t
            ON {join_condition}
    """).fetchone()[0]

    source_count = con.execute(
        f"SELECT COUNT(*) FROM {source}"
    ).fetchone()[0]

    # Identify records where at least one non-key value changed.
    changed_condition = " OR ".join(
        f"t.{col} IS DISTINCT FROM s.{col}"
        for col in non_key_columns
    )

    if changed_condition:
        updated_count = con.execute(f"""
            SELECT COUNT(*)
            FROM {source} s
            INNER JOIN {table} t
                ON {join_condition}
            WHERE {changed_condition}
        """).fetchone()[0]
    else:
        updated_count = 0

    inserted_count = source_count - matched_count
    unchanged_count = matched_count - updated_count

    # Update only changed records.
    update_clause = ", ".join(
        f"{col} = s.{col}" for col in non_key_columns
    )

    insert_columns = ", ".join(target_columns)
    insert_values = ", ".join(
        f"s.{col}" for col in target_columns
    )

    merge_sql = f"""
        MERGE INTO {table} t
        USING {source} s
        ON {join_condition}

        WHEN MATCHED AND ({changed_condition}) THEN
            UPDATE SET {update_clause}

        WHEN NOT MATCHED THEN
            INSERT ({insert_columns})
            VALUES ({insert_values})
    """

    if changed_condition:
        con.execute(merge_sql)
    else:
        # This branch is only relevant if a table has key columns only.
        con.execute(f"""
            MERGE INTO {table} t
            USING {source} s
            ON {join_condition}
            WHEN NOT MATCHED THEN
                INSERT ({insert_columns})
                VALUES ({insert_values})
        """)

    print(f"\n--- {table} ---")
    print(f"Inserted:  {inserted_count:,}")
    print(f"Updated:   {updated_count:,}")
    print(f"Unchanged: {unchanged_count:,}")


def export_to_parquet(con):
    processed_dir = BASE_DIR / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== EXPORTING PARQUET FILES ===")

    for table in TABLE_CONFIG:
        output_path = (
            processed_dir / f"{table}.parquet"
        ).as_posix()

        con.execute(f"""
            COPY (SELECT * FROM {table})
            TO '{output_path}'
            (FORMAT PARQUET)
        """)

        print(f"[EXPORTED] {table}.parquet")



def main():
    con = duckdb.connect(str(DB_PATH))
    transaction_open = False

    try:
        print("=== INCREMENTAL INGESTION ===")

        con.execute("BEGIN TRANSACTION")
        transaction_open = True

        for table, config in TABLE_CONFIG.items():
            load_and_stage(con, table, config)

        print("\n=== MERGING TABLES ===")

        for table, config in TABLE_CONFIG.items():
            merge_table(con, table, config)

        con.execute("COMMIT")
        transaction_open = False

        export_to_parquet(con)

        print("\nAll tables merged and exported successfully.")

    except Exception:
        if transaction_open:
            con.execute("ROLLBACK")
        raise

    finally:
        con.close()


if __name__ == "__main__":
    main()
