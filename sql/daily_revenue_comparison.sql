
WITH order_sales AS (
    SELECT
        o.order_id,
        o.order_date,
        o.order_discount,
        SUM(oi.quantity * oi.unit_price) AS gross_product_value,
        SUM(oi.line_discount) AS line_discounts
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    WHERE o.status != 'cancelled'
    GROUP BY o.order_id, o.order_date, o.order_discount
),
daily_sales AS (
    SELECT
        order_date AS report_date,
        SUM(
            gross_product_value
            - line_discounts
            - order_discount
        ) AS sales_after_discounts
    FROM order_sales
    GROUP BY order_date
),
daily_refunds AS (
    SELECT
        refund_date AS report_date,
        SUM(refund_amount) AS total_refunds
    FROM refunds
    WHERE refund_date <= CURRENT_DATE - INTERVAL 1 DAY
    GROUP BY refund_date
),
all_dates AS (
    SELECT report_date FROM daily_sales
    UNION
    SELECT report_date FROM daily_refunds
),
daily_net AS (
    SELECT
        d.report_date,
        COALESCE(s.sales_after_discounts, 0)
            - COALESCE(r.total_refunds, 0) AS net_revenue
    FROM all_dates d
    LEFT JOIN daily_sales s USING (report_date)
    LEFT JOIN daily_refunds r USING (report_date)
),
comparisons AS (
    SELECT
        today.report_date,
        today.net_revenue,
        yesterday.net_revenue AS previous_date_revenue,
        last_week.net_revenue AS previous_week_revenue
    FROM daily_net today
    LEFT JOIN daily_net yesterday
        ON yesterday.report_date = today.report_date - INTERVAL 1 DAY
    LEFT JOIN daily_net last_week
        ON last_week.report_date = today.report_date - INTERVAL 7 DAY
)


SELECT
    report_date,
    net_revenue,
    previous_date_revenue,
    previous_week_revenue,

    ROUND(
        100.0 * (net_revenue - previous_date_revenue)
        / NULLIF(previous_date_revenue, 0), 2
    ) AS change_vs_previous_date_pct,

    ROUND(
        100.0 * (net_revenue - previous_week_revenue)
        / NULLIF(previous_week_revenue, 0), 2
    ) AS change_vs_previous_week_pct,

    CASE
        WHEN previous_date_revenue IS NULL
          OR previous_date_revenue <= 0
        THEN 'NO BASELINE'
        WHEN ABS(
            100.0 * (net_revenue - previous_date_revenue)
            / previous_date_revenue
        ) >= 10
        THEN 'ALERT'
        ELSE 'NORMAL'
    END AS previous_date_status,

    CASE
        WHEN previous_week_revenue IS NULL
          OR previous_week_revenue <= 0
        THEN 'NO BASELINE'
        WHEN ABS(
            100.0 * (net_revenue - previous_week_revenue)
            / previous_week_revenue
        ) >= 10
        THEN 'ALERT'
        ELSE 'NORMAL'
    END AS previous_week_status,

    CASE
        WHEN (
            previous_date_revenue > 0
            AND ABS(
                100.0 * (net_revenue - previous_date_revenue)
                / previous_date_revenue
            ) >= 10
        )
        OR (
            previous_week_revenue > 0
            AND ABS(
                100.0 * (net_revenue - previous_week_revenue)
                / previous_week_revenue
            ) >= 10
        )
        THEN 'ALERT'
        WHEN previous_date_revenue IS NULL
          OR previous_date_revenue <= 0
          OR previous_week_revenue IS NULL
          OR previous_week_revenue <= 0
        THEN 'INCOMPLETE'
        ELSE 'NORMAL'
    END AS overall_status,
        CASE
        WHEN (
            previous_date_revenue > 0
            AND ABS(
                100.0 * (net_revenue - previous_date_revenue)
                / previous_date_revenue
            ) >= 10
        )
        AND (
            previous_week_revenue > 0
            AND ABS(
                100.0 * (net_revenue - previous_week_revenue)
                / previous_week_revenue
            ) >= 10
        )
        THEN 'BOTH'

        WHEN previous_date_revenue > 0
        AND ABS(
            100.0 * (net_revenue - previous_date_revenue)
            / previous_date_revenue
        ) >= 10
        THEN 'PREVIOUS DAY'

        WHEN previous_week_revenue > 0
        AND ABS(
            100.0 * (net_revenue - previous_week_revenue)
            / previous_week_revenue
        ) >= 10
        THEN 'SAME WEEKDAY LAST WEEK'

        ELSE 'NONE'
    END AS alert_trigger,

    10 AS alert_threshold_pct

FROM comparisons
ORDER BY report_date;
