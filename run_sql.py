
from pathlib import Path
import sys
import duckdb

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ecommerce.duckdb"
SQL_DIR = BASE_DIR / "sql"


def main():
    if len(sys.argv) != 2:
        print("Usage: python run_sql.py <query_file.sql>")
        print("Example: python run_sql.py daily_revenue.sql")
        sys.exit(1)

    sql_file = SQL_DIR / sys.argv[1]

    if sql_file.suffix.lower() != ".sql" or not sql_file.is_file():
        print(f"SQL file not found: {sql_file}")
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        query = sql_file.read_text(encoding="utf-8")
        result = con.execute(query).df()

        print(f"\n=== RESULTS: {sql_file.name} ===")
        print(f"Total rows: {len(result):,}\n")

        if result.empty:
            print("No rows returned.")
            return

        # Display the first 10 rows with all columns
        display_result = result.head(10).copy()

        # Round numeric columns for readability
        for column in display_result.select_dtypes(include="number").columns:
            display_result[column] = display_result[column].round(2)

        # Generic output: works with any query's column names
        print(display_result.to_string(index=False))

        if len(result) > 10:
            print(f"\nShowing 10 of {len(result):,} rows.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
