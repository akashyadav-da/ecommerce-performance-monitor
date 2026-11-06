
WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

order_level_sales AS (
    SELECT
        o.order_id,
        CAST(o.order_date AS DATE) AS event_date,
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

regional_sales AS (
    SELECT
        region,
        event_date,
        SUM(gross_sales - line_discounts - order_discount)
            AS sales_after_discounts
    FROM order_level_sales
    GROUP BY region, event_date
),

regional_refunds AS (
    SELECT
        o.region,
        CAST(r.refund_date AS DATE) AS event_date,
        SUM(r.refund_amount) AS total_refunds
    FROM refunds r
    JOIN orders o
        ON r.order_id = o.order_id
    CROSS JOIN date_params dp
    WHERE CAST(r.refund_date AS DATE)
          IN (dp.comparison_date, dp.report_date)
      AND CAST(r.refund_date AS DATE) <= dp.report_date
    GROUP BY o.region, CAST(r.refund_date AS DATE)
),

all_regions_dates AS (
    SELECT region, event_date FROM regional_sales
    UNION
    SELECT region, event_date FROM regional_refunds
),

regional_net_revenue AS (
    SELECT
        d.region,
        d.event_date,
        COALESCE(s.sales_after_discounts, 0) AS sales_after_discounts,
        COALESCE(r.total_refunds, 0) AS total_refunds,
        COALESCE(s.sales_after_discounts, 0)
            - COALESCE(r.total_refunds, 0) AS net_revenue
    FROM all_regions_dates d
    LEFT JOIN regional_sales s
        ON d.region = s.region
       AND d.event_date = s.event_date
    LEFT JOIN regional_refunds r
        ON d.region = r.region
       AND d.event_date = r.event_date
)

SELECT
    r.region,
    dp.comparison_date,
    dp.report_date,

    ROUND(SUM(CASE
        WHEN r.event_date = dp.comparison_date
        THEN r.net_revenue ELSE 0
    END), 2) AS previous_net_revenue,

    ROUND(SUM(CASE
        WHEN r.event_date = dp.report_date
        THEN r.net_revenue ELSE 0
    END), 2) AS current_net_revenue,

    ROUND(
        SUM(CASE
            WHEN r.event_date = dp.report_date
            THEN r.net_revenue ELSE 0
        END)
        -
        SUM(CASE
            WHEN r.event_date = dp.comparison_date
            THEN r.net_revenue ELSE 0
        END),
        2
    ) AS net_revenue_change

FROM regional_net_revenue r
CROSS JOIN date_params dp
GROUP BY r.region, dp.comparison_date, dp.report_date
ORDER BY net_revenue_change ASC;
