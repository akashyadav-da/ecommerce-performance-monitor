```Business question: How much money was refunded on each day```

SELECT
    refund_date,
    SUM(refund_amount) AS total_refunds,
    COUNT(*) AS refund_count
FROM refunds
GROUP BY refund_date
ORDER BY refund_date;
