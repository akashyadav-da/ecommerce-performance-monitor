WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

order_level_sales AS (
    SELECT
        o.order_id,
        CAST(o.order_date AS DATE) AS order_date,
        o.channel,
        o.order_discount,
        SUM(oi.quantity * oi.unit_price) AS gross_sales,
        SUM(oi.line_discount) AS line_discounts
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    CROSS JOIN date_params p
    WHERE o.status != 'cancelled'
      AND CAST(o.order_date AS DATE)
          IN (p.report_date, p.comparison_date)
    GROUP BY
        o.order_id,
        CAST(o.order_date AS DATE),
        o.channel,
        o.order_discount
),

channel_sales AS (
    SELECT
        channel,

        SUM(
            CASE WHEN order_date = p.comparison_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0 END
        ) AS previous_sales,

        SUM(
            CASE WHEN order_date = p.report_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0 END
        ) AS current_sales

    FROM order_level_sales
    CROSS JOIN date_params p
    GROUP BY channel
),

channel_movement AS (
    SELECT
        channel,
        previous_sales,
        current_sales,
        current_sales - previous_sales AS revenue_change,

        100.0 * (current_sales - previous_sales)
            / NULLIF(previous_sales, 0) AS change_pct

    FROM channel_sales
),

total_movement AS (
    SELECT
        SUM(previous_sales - current_sales) AS total_decline
    FROM channel_sales
)

SELECT
    channel,
    p.comparison_date,
    p.report_date,

    ROUND(previous_sales, 2) AS previous_sales,
    ROUND(current_sales, 2) AS current_sales,
    ROUND(revenue_change, 2) AS revenue_change,
    ROUND(change_pct, 2) AS change_pct,

    ROUND(
        100.0 * (previous_sales - current_sales)
        / NULLIF(tm.total_decline, 0),
        2
    ) AS decline_contribution_pct

FROM channel_movement
CROSS JOIN total_movement tm
CROSS JOIN date_params p
ORDER BY revenue_change ASC;