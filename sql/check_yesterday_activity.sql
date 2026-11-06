
SELECT
    CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,

    (
        SELECT COUNT(*)
        FROM orders
        WHERE CAST(order_date AS DATE) = CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE)
          AND status != 'cancelled'
    ) AS valid_orders,

    (
        SELECT COUNT(*)
        FROM refunds
        WHERE CAST(refund_date AS DATE) = CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE)
    ) AS refund_records,

    (
        SELECT ROUND(COALESCE(SUM(refund_amount), 0), 2)
        FROM refunds
        WHERE CAST(refund_date AS DATE) = CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE)
    ) AS refund_amount;
