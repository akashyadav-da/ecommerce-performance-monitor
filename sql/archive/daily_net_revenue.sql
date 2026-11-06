
WITH daily_sales AS (
    SELECT
        order_date AS report_date,
        SUM(
            gross_product_value
            - line_discounts
            - order_discount
        ) AS sales_after_discounts
    FROM (
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
    ) order_sales
    GROUP BY order_date
),
daily_refunds AS (
    SELECT
        refund_date AS report_date,
        SUM(refund_amount) AS total_refunds
    FROM refunds
    GROUP BY refund_date
),
all_dates AS (
    SELECT report_date FROM daily_sales
    UNION
    SELECT report_date FROM daily_refunds
)
SELECT
    d.report_date,
    COALESCE(s.sales_after_discounts, 0) AS sales_after_discounts,
    COALESCE(r.total_refunds, 0) AS total_refunds,
    COALESCE(s.sales_after_discounts, 0)
        - COALESCE(r.total_refunds, 0) AS net_revenue
FROM all_dates d
LEFT JOIN daily_sales s
    ON d.report_date = s.report_date
LEFT JOIN daily_refunds r
    ON d.report_date = r.report_date
ORDER BY d.report_date;
