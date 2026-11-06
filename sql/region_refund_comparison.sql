WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

regional_refunds AS (
    SELECT
        o.region,
        CAST(r.refund_date AS DATE) AS refund_date,
        r.refund_id,
        r.refund_amount
    FROM refunds r
    JOIN orders o
        ON r.order_id = o.order_id
    CROSS JOIN date_params dp
    WHERE CAST(r.refund_date AS DATE)
          IN (dp.comparison_date, dp.report_date)
      AND CAST(r.refund_date AS DATE) <= dp.report_date
),

refund_summary AS (
    SELECT
        region,

        COUNT(CASE
            WHEN refund_date = dp.comparison_date
            THEN refund_id
        END) AS previous_refund_count,

        COUNT(CASE
            WHEN refund_date = dp.report_date
            THEN refund_id
        END) AS current_refund_count,

        SUM(CASE
            WHEN refund_date = dp.comparison_date
            THEN refund_amount ELSE 0
        END) AS previous_refunds,

        SUM(CASE
            WHEN refund_date = dp.report_date
            THEN refund_amount ELSE 0
        END) AS current_refunds

    FROM regional_refunds
    CROSS JOIN date_params dp
    GROUP BY region
)

SELECT
    rs.region,
    dp.comparison_date,
    dp.report_date,

    rs.previous_refund_count,
    rs.current_refund_count,

    ROUND(rs.previous_refunds, 2) AS previous_refunds,
    ROUND(rs.current_refunds, 2) AS current_refunds,

    ROUND(
        rs.current_refunds - rs.previous_refunds, 2
    ) AS refund_change

FROM refund_summary rs
CROSS JOIN date_params dp
ORDER BY refund_change DESC;