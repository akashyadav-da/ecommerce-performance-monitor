WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

order_level_sales AS (
    SELECT
        o.order_id,
        CAST(o.order_date AS DATE) AS order_date,
        o.region,
        SUM(oi.quantity * oi.unit_price) AS gross_sales,
        SUM(oi.line_discount) AS line_discounts,
        o.order_discount
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    CROSS JOIN date_params dp
    WHERE o.status != 'cancelled'
      AND CAST(o.order_date AS DATE)
          IN (dp.comparison_date, dp.report_date)
    GROUP BY
        o.order_id,
        CAST(o.order_date AS DATE),
        o.region,
        o.order_discount
),

region_sales AS (
    SELECT
        region,

        SUM(CASE
            WHEN order_date = dp.comparison_date
            THEN 1 ELSE 0
        END) AS previous_orders,

        SUM(CASE
            WHEN order_date = dp.report_date
            THEN 1 ELSE 0
        END) AS current_orders,

        SUM(CASE
            WHEN order_date = dp.comparison_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0
        END) AS previous_sales,

        SUM(CASE
            WHEN order_date = dp.report_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0
        END) AS current_sales

    FROM order_level_sales
    CROSS JOIN date_params dp
    GROUP BY region
)

SELECT
    rs.region,
    dp.comparison_date,
    dp.report_date,
    rs.previous_orders,
    rs.current_orders,
    ROUND(rs.previous_sales, 2) AS previous_sales,
    ROUND(rs.current_sales, 2) AS current_sales,
    ROUND(rs.current_sales - rs.previous_sales, 2)
        AS revenue_change,

    ROUND(
        100.0 * (rs.current_sales - rs.previous_sales)
        / NULLIF(rs.previous_sales, 0),
        2
    ) AS revenue_change_pct

FROM region_sales rs
CROSS JOIN date_params dp
ORDER BY revenue_change ASC;