SELECT
    (SELECT MAX(order_date) FROM orders) AS latest_order_date,
    (SELECT MAX(refund_date) FROM refunds) AS latest_refund_date,
    CURRENT_DATE AS today;