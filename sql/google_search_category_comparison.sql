WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

product_level_sales AS (
    SELECT
        o.order_id,
        CAST(o.order_date AS DATE) AS order_date,
        o.channel,
        p.category,
        oi.quantity,
        oi.unit_price,
        oi.line_discount,
        o.order_discount
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    JOIN products p
        ON oi.product_id = p.product_id
    CROSS JOIN date_params dp
    WHERE o.status != 'cancelled'
      AND o.channel = 'Google Search'
      AND CAST(o.order_date AS DATE)
          IN (dp.comparison_date, dp.report_date)
),

order_category_sales AS (
    SELECT
        order_id,
        order_date,
        category,
        MAX(order_discount) AS order_discount,
        SUM(quantity * unit_price - line_discount)
            AS category_sales_before_order_discount
    FROM product_level_sales
    GROUP BY order_id, order_date, category
),

order_totals AS (
    SELECT
        order_id,
        SUM(category_sales_before_order_discount)
            AS total_order_sales
    FROM order_category_sales
    GROUP BY order_id
),

allocated_category_sales AS (
    SELECT
        ocs.order_id,
        ocs.order_date,
        ocs.category,
        ocs.category_sales_before_order_discount,
        CASE
            WHEN ot.total_order_sales > 0
            THEN ocs.order_discount
                 * ocs.category_sales_before_order_discount
                 / ot.total_order_sales
            ELSE 0
        END AS allocated_order_discount
    FROM order_category_sales ocs
    JOIN order_totals ot
        ON ocs.order_id = ot.order_id
),

category_summary AS (
    SELECT
        category,
        order_date,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(
            category_sales_before_order_discount
            - allocated_order_discount
        ) AS category_sales_after_discounts
    FROM allocated_category_sales
    GROUP BY category, order_date
)

SELECT
    cs.category,
    dp.comparison_date,
    dp.report_date,

    COALESCE(MAX(CASE
        WHEN cs.order_date = dp.comparison_date
        THEN cs.total_orders
    END), 0) AS previous_orders,

    COALESCE(MAX(CASE
        WHEN cs.order_date = dp.report_date
        THEN cs.total_orders
    END), 0) AS current_orders,

    ROUND(COALESCE(MAX(CASE
        WHEN cs.order_date = dp.comparison_date
        THEN cs.category_sales_after_discounts
    END), 0), 2) AS previous_sales,

    ROUND(COALESCE(MAX(CASE
        WHEN cs.order_date = dp.report_date
        THEN cs.category_sales_after_discounts
    END), 0), 2) AS current_sales

FROM category_summary cs
CROSS JOIN date_params dp
GROUP BY
    cs.category,
    dp.comparison_date,
    dp.report_date
ORDER BY previous_sales DESC;