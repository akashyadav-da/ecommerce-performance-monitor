
WITH daily_line_sales AS (
    SELECT
        o.order_id,
        o.order_date,
        SUM(oi.quantity * oi.unit_price) AS gross_product_value,
        SUM(oi.line_discount) AS line_discounts
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    WHERE o.status != 'cancelled'
    GROUP BY o.order_id, o.order_date
)
SELECT
    d.order_date,
    SUM(d.gross_product_value) AS gross_product_value,
    SUM(d.line_discounts) AS line_discounts,
    SUM(o.order_discount) AS order_discounts,
    SUM(
        d.gross_product_value
        - d.line_discounts
        - o.order_discount
    ) AS sales_after_discounts
FROM daily_line_sales d
JOIN orders o
    ON d.order_id = o.order_id
GROUP BY d.order_date
ORDER BY d.order_date;
