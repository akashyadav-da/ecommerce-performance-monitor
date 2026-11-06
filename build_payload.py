from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ecommerce.duckdb"
SQL_DIR = BASE_DIR / "sql"
REPORT_DIR = BASE_DIR / "reports"
RAW_DIR = BASE_DIR / "data" / "raw"

TEST_AS_OF_DATE = "2026-11-01"

def normalize_dates(records):
    for record in records:
        for key, value in record.items():
            if (
                isinstance(value, str)
                and (key.endswith("_date") or key in {"report_date", "comparison_date"})
            ):
                record[key] = value[:10]
    return records


def execute_query(con, filename):
    """Execute a SQL file and return its results as JSON-safe records."""
    sql_file = SQL_DIR / filename

    if not sql_file.is_file():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")

    query = sql_file.read_text(encoding="utf-8")

    if TEST_AS_OF_DATE:
     query = query.replace(
        "CURRENT_DATE",
        f"DATE '{TEST_AS_OF_DATE}'"
    )

    result = con.execute(query).df()

    records = json.loads(result.to_json(orient="records", date_format="iso"))
    return normalize_dates(records)


def run_data_quality_checks():
    """
    Run the existing relationship and refund-value checks before building
    the report. FAIL blocks report generation; WARN is non-blocking.
    """
    required_files = {
        "orders": RAW_DIR / "orders.csv",
        "order_items": RAW_DIR / "order_items.csv",
        "products": RAW_DIR / "products.csv",
        "refunds": RAW_DIR / "refunds.csv",
    }

    missing_files = [str(path) for path in required_files.values() if not path.is_file()]
    if missing_files:
        return {
            "status": "FAIL",
            "errors": [f"Required raw data file is missing: {path}" for path in missing_files],
            "warnings": [],
        }

    orders = pd.read_csv(required_files["orders"])
    items = pd.read_csv(required_files["order_items"])
    products = pd.read_csv(required_files["products"])
    refunds = pd.read_csv(required_files["refunds"])

    errors = []
    warnings = []

    # Check required columns before running the detailed validations.
    required_columns = {
        "orders": {"order_id", "status", "order_discount"},
        "order_items": {"order_id", "product_id", "quantity", "unit_price", "line_discount"},
        "products": {"product_id"},
        "refunds": {"order_id", "product_id", "refund_amount", "refund_id"},
    }
    frames = {
        "orders": orders,
        "order_items": items,
        "products": products,
        "refunds": refunds,
    }

    for name, columns in required_columns.items():
        missing = columns - set(frames[name].columns)
        if missing:
            errors.append(
                f"{name}.csv is missing required columns: {', '.join(sorted(missing))}"
            )

    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    # 1. Order IDs: conflicting duplicates can make order-level metrics unreliable.
    duplicate_orders = orders[orders["order_id"].duplicated(keep=False)]
    if not duplicate_orders.empty:
        conflicting_ids = (
            duplicate_orders.groupby("order_id", dropna=False)
            .apply(lambda group: len(group.drop_duplicates()) > 1, include_groups=False)
        )
        conflicting_count = int(conflicting_ids.sum())
        identical_count = int(len(duplicate_orders) - duplicate_orders["order_id"].nunique())

        if conflicting_count:
            errors.append(
                f"{conflicting_count} order IDs have conflicting duplicate records."
            )
        if identical_count:
            warnings.append(
                f"{identical_count} repeated order rows are exact duplicates; "
                "confirm the cleaning step removes them before loading."
            )

    # 2. Referential integrity.
    unknown_order_items = int((~items["order_id"].isin(orders["order_id"])).sum())
    unknown_product_items = int((~items["product_id"].isin(products["product_id"])).sum())
    unknown_refund_orders = int((~refunds["order_id"].isin(orders["order_id"])).sum())
    unknown_refund_products = int((~refunds["product_id"].isin(products["product_id"])).sum())

    if unknown_order_items:
        errors.append(f"{unknown_order_items} order-item rows reference unknown order IDs.")
    if unknown_product_items:
        errors.append(f"{unknown_product_items} order-item rows reference unknown product IDs.")
    if unknown_refund_orders:
        errors.append(f"{unknown_refund_orders} refund rows reference unknown order IDs.")
    if unknown_refund_products:
        errors.append(f"{unknown_refund_products} refund rows reference unknown product IDs.")

    # 3. Product ID uniqueness.
    duplicate_product_ids = int(products["product_id"].duplicated().sum())
    if duplicate_product_ids:
        errors.append(f"{duplicate_product_ids} duplicate product IDs were found.")

    # 4. Every non-cancelled order must have item data.
    item_order_ids = set(items["order_id"].dropna())
    valid_orders = orders[orders["status"].astype(str).str.lower() != "cancelled"]
    orders_without_items = int((~valid_orders["order_id"].isin(item_order_ids)).sum())
    if orders_without_items:
        errors.append(
            f"{orders_without_items} non-cancelled orders have no matching order-item rows."
        )

    # 5. Refund amounts must not exceed the order's value after all discounts.
    items = items.copy()
    orders = orders.copy()
    refunds = refunds.copy()

    numeric_columns = {
        "order_items": ["quantity", "unit_price", "line_discount"],
        "orders": ["order_discount"],
        "refunds": ["refund_amount"],
    }

    for name, columns in numeric_columns.items():
        frame = frames[name]
        for column in columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Reassign converted frames.
    orders = frames["orders"]
    items = frames["order_items"]
    refunds = frames["refunds"]

    if (
        items[["quantity", "unit_price", "line_discount"]].isna().any().any()
        or orders["order_discount"].isna().any()
        or refunds["refund_amount"].isna().any()
    ):
        errors.append("Missing or non-numeric values found in quantity, price, discount, or refund fields.")

    if (items["quantity"] <= 0).any():
        errors.append("Order items contain zero or negative quantities.")
    if (items["unit_price"] < 0).any() or (items["line_discount"] < 0).any():
        errors.append("Order items contain negative prices or line discounts.")
    if (orders["order_discount"] < 0).any():
        errors.append("Orders contain negative order discounts.")
    if (refunds["refund_amount"] < 0).any():
        errors.append("Refunds contain negative refund amounts.")

    # Continue refund math only when its numeric inputs are usable.
    numeric_inputs_valid = not (
        items[["quantity", "unit_price", "line_discount"]].isna().any().any()
        or orders["order_discount"].isna().any()
        or refunds["refund_amount"].isna().any()
    )

    if numeric_inputs_valid:
        items["line_gross"] = items["quantity"] * items["unit_price"]
        item_totals = items.groupby("order_id", as_index=False).agg(
            gross_product_value=("line_gross", "sum"),
            line_discounts=("line_discount", "sum"),
        )

        audit = orders.merge(item_totals, on="order_id", how="left")
        audit["value_after_all_discounts"] = (
            audit["gross_product_value"]
            - audit["line_discounts"]
            - audit["order_discount"]
        )

        refund_totals = refunds.groupby("order_id", as_index=False).agg(
            total_refunds=("refund_amount", "sum")
        )
        audit = audit.merge(refund_totals, on="order_id", how="left")
        audit["total_refunds"] = audit["total_refunds"].fillna(0)

        refund_exceptions = audit[
            (audit["status"].astype(str).str.lower() != "cancelled")
            & (
                audit["total_refunds"]
                > audit["value_after_all_discounts"] + 0.01
            )
        ]

        if not refund_exceptions.empty:
            errors.append(
                f"{len(refund_exceptions)} non-cancelled orders have refunds "
                "exceeding their value after discounts."
            )

    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }


def validate_payload(payload):
    required_sections = {
        "report_metadata",
        "kpi_summary",
        "alert_summary",
        "investigation",
        "data_quality",
        "limitations",
    }

    missing = required_sections - payload.keys()
    if missing:
        raise ValueError(f"Missing payload sections: {missing}")

    valid_statuses = {"ALERT", "NORMAL", "INCOMPLETE"}
    status = payload["alert_summary"]["overall_status"]

    if status not in valid_statuses:
        raise ValueError(f"Invalid alert status: {status}")

    required_alert_fields = {
        "alert_trigger",
        "alert_threshold_pct",
        "previous_date_revenue",
        "previous_week_revenue",
        "change_vs_previous_date_pct",
        "change_vs_previous_week_pct",
    }
    missing_alert_fields = required_alert_fields - payload["alert_summary"].keys()
    if missing_alert_fields:
        raise ValueError(
            f"Missing alert-summary fields: {', '.join(sorted(missing_alert_fields))}"
        )

    for section, records in payload["investigation"].items():
        if not isinstance(records, list):
            raise ValueError(
                f"Investigation section '{section}' must contain a list."
            )

    if payload["data_quality"]["status"] == "FAIL":
        raise ValueError("Critical data-quality failure: report generation is blocked.")

class IncompleteDataError(Exception):
    pass

def main():
    REPORT_DIR.mkdir(exist_ok=True)

    # 1. Run data-quality checks before querying or creating a report.
    data_quality = run_data_quality_checks()

    print(f"Data quality status: {data_quality['status']}")
    for warning in data_quality["warnings"]:
        print(f"WARNING: {warning}")
    for error in data_quality["errors"]:
        print(f"ERROR: {error}")

    if data_quality["status"] == "FAIL":
        print("\nReport generation BLOCKED. No new payload was created.")
        raise SystemExit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        # 2. Collect the daily KPI and alert results.
        daily_report = execute_query(con, "daily_revenue_comparison.sql")
        daily_activity = execute_query(con, "check_yesterday_activity.sql")

        if not daily_report:
            raise ValueError("Daily revenue comparison returned no results.")
        if not daily_activity:
            raise ValueError("Daily activity query returned no results.")

        # Select exactly yesterday's report using Indian Standard Time.
        if TEST_AS_OF_DATE:
         report_date = (
        datetime.fromisoformat(TEST_AS_OF_DATE).date() - timedelta(days=1)
        ).isoformat()
        else:
         report_date = (
        datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)
        ).isoformat()

        # Check whether source orders cover the requested report date.
        latest_order_date = con.execute("""
            SELECT MAX(CAST(order_date AS DATE))
            FROM orders
        """).fetchone()[0]

        if latest_order_date is None or latest_order_date < datetime.fromisoformat(report_date).date():
            raise IncompleteDataError(
            f"Order data ends on {latest_order_date}, "
            f"but the requested report date is {report_date}."
            )
        

        matching_reports = [
            row for row in daily_report
            if row.get("report_date") == report_date
        ]

        if not matching_reports:
            raise ValueError(
                f"No revenue comparison data found for yesterday ({report_date}). "
                "Report generation blocked."
            )

        kpis = matching_reports[0]
        activity = daily_activity[0]

        # 3. Determine whether deeper investigation is required.
        alert_status = str(kpis["overall_status"]).upper()
        investigation = {}

        if alert_status == "ALERT":
            investigation_queries = {
                "channel_revenue": "channel_revenue_comparison.sql",
                "channel_orders_aov": "channel_orders_aov_comparison.sql",
                "google_search_category": "google_search_category_comparison.sql",
                "google_search_product": "google_search_product_comparison.sql",
                "regional_revenue": "region_revenue_comparison.sql",
                "regional_refunds": "region_refund_comparison.sql",
                "regional_net_revenue": "region_net_revenue_comparison.sql",
            }

            for section, filename in investigation_queries.items():
                investigation[section] = execute_query(con, filename)

        # 4. Assemble the evidence payload.
        payload = {
            "report_metadata": {
                "report_date": kpis["report_date"][:10],
                "generated_at": datetime.now(
                    ZoneInfo("Asia/Kolkata")
                ).isoformat(),
                "currency": "INR",
                "timezone": "Asia/Kolkata",
            },
            "kpi_summary": {
                "net_revenue": kpis["net_revenue"],
                "valid_orders": activity["valid_orders"],
                "refund_records": activity["refund_records"],
                "refund_amount": activity["refund_amount"],
            },
            "alert_summary": {
                "previous_date_revenue": kpis["previous_date_revenue"],
                "previous_week_revenue": kpis["previous_week_revenue"],
                "change_vs_previous_date_pct": kpis["change_vs_previous_date_pct"],
                "change_vs_previous_week_pct": kpis["change_vs_previous_week_pct"],
                "alert_trigger": kpis["alert_trigger"],
                "alert_threshold_pct": kpis["alert_threshold_pct"],
                "overall_status": alert_status,
            },
            "investigation": investigation,
            "data_quality": data_quality,
            "limitations": [
                "Investigation is performed only when an alert is triggered.",
                "Revenue movements identify changes, not their causes.",
                "Google Search category and product analysis covers that channel only.",
            ],
        }

        validate_payload(payload)
        print("\nPayload structure validation: PASSED")

        # 5. Save only after all checks pass.
        output_file = REPORT_DIR / "latest_payload.json"
        output_file.write_text(
            json.dumps(payload, indent=4, allow_nan=False),
            encoding="utf-8",
        )

        print(f"\nPayload created: {output_file}")
        print(f"Report date: {payload['report_metadata']['report_date']}")
        print(f"Alert status: {alert_status}")
        print(f"Investigation sections: {len(investigation)}")

    except IncompleteDataError as error:
        incomplete_payload = {
            "report_metadata": {
                "report_date": report_date,
                "generated_at": datetime.now(
                    ZoneInfo("Asia/Kolkata")
                ).isoformat(),
                "currency": "INR",
                "timezone": "Asia/Kolkata",
            },
            "kpi_summary": {
                "net_revenue": None,
                "valid_orders": None,
                "refund_records": None,
                "refund_amount": None,
            },
            "alert_summary": {
                "previous_date_revenue": None,
                "previous_week_revenue": None,
                "change_vs_previous_date_pct": None,
                "change_vs_previous_week_pct": None,
                "alert_trigger": "NOT_EVALUATED",
                "alert_threshold_pct": 10,
                "overall_status": "INCOMPLETE",
            },
            "investigation": {},
            "data_quality": data_quality,
            "limitations": [
                str(error),
                "Performance analysis was skipped because source data does not cover the reporting date.",
            ],
        }

        validate_payload(incomplete_payload)

        output_file = REPORT_DIR / "latest_payload.json"
        output_file.write_text(
            json.dumps(incomplete_payload, indent=4, allow_nan=False),
            encoding="utf-8",
        )

        print("\nReport status: INCOMPLETE")
        print(f"Reason: {error}")
        print(f"Coverage warning payload created: {output_file}")

    finally:
        con.close()


if __name__ == "__main__":
    main()