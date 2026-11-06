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
          IN (p.comparison_date, p.report_date)
    GROUP BY
        o.order_id,
        CAST(o.order_date AS DATE),
        o.channel,
        o.order_discount
),

channel_sales AS (
    SELECT
        channel,

        COUNT(CASE
            WHEN order_date = p.comparison_date THEN order_id
        END) AS previous_orders,

        COUNT(CASE
            WHEN order_date = p.report_date THEN order_id
        END) AS current_orders,

        SUM(CASE
            WHEN order_date = p.comparison_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0
        END) AS previous_sales,

        SUM(CASE
            WHEN order_date = p.report_date
            THEN gross_sales - line_discounts - order_discount
            ELSE 0
        END) AS current_sales

    FROM order_level_sales
    CROSS JOIN date_params p
    GROUP BY channel
),

channel_metrics AS (
    SELECT
        *,
        previous_sales / NULLIF(previous_orders, 0) AS previous_aov,
        current_sales / NULLIF(current_orders, 0) AS current_aov
    FROM channel_sales
)

SELECT
    channel,
    p.comparison_date,
    p.report_date,

    previous_orders,
    current_orders,

    ROUND(previous_sales, 2) AS previous_sales,
    ROUND(current_sales, 2) AS current_sales,

    ROUND(previous_aov, 2) AS previous_aov,
    ROUND(current_aov, 2) AS current_aov,

    ROUND(
        100.0 * (current_orders - previous_orders)
        / NULLIF(previous_orders, 0),
        2
    ) AS order_change_pct,

    ROUND(
        100.0 * (current_aov - previous_aov)
        / NULLIF(previous_aov, 0),
        2
    ) AS aov_change_pct

FROM channel_metrics
CROSS JOIN date_params p
ORDER BY channel;