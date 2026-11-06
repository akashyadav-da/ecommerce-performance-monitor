WITH date_params AS (
    SELECT
        CAST(CURRENT_DATE - INTERVAL 1 DAY AS DATE) AS report_date,
        CAST(CURRENT_DATE - INTERVAL 8 DAY AS DATE) AS comparison_date
),

product_sales AS (
    SELECT
        o.order_id,
        CAST(o.order_date AS DATE) AS order_date,
        p.product_id,
        p.product_name,
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

order_product_sales AS (
    SELECT
        order_id,
        order_date,
        product_id,
        product_name,
        category,
        SUM(quantity) AS units_sold,
        SUM(quantity * unit_price - line_discount)
            AS sales_before_order_discount,
        MAX(order_discount) AS order_discount
    FROM product_sales
    GROUP BY
        order_id,
        order_date,
        product_id,
        product_name,
        category
),

order_totals AS (
    SELECT
        order_id,
        SUM(sales_before_order_discount) AS total_order_sales
    FROM order_product_sales
    GROUP BY order_id
),

allocated_product_sales AS (
    SELECT
        p.order_id,
        p.order_date,
        p.product_id,
        p.product_name,
        p.category,
        p.units_sold,
        p.sales_before_order_discount,
        CASE
            WHEN t.total_order_sales > 0
            THEN p.order_discount
                 * p.sales_before_order_discount
                 / t.total_order_sales
            ELSE 0
        END AS allocated_order_discount
    FROM order_product_sales p
    JOIN order_totals t
        ON p.order_id = t.order_id
),

product_summary AS (
    SELECT
        product_id,
        product_name,
        category,
        order_date,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(units_sold) AS units_sold,
        SUM(
            sales_before_order_discount - allocated_order_discount
        ) AS sales_after_discounts
    FROM allocated_product_sales
    GROUP BY product_id, product_name, category, order_date
)

SELECT
    ps.product_id,
    ps.product_name,
    ps.category,
    dp.comparison_date,
    dp.report_date,

    COALESCE(SUM(CASE
        WHEN ps.order_date = dp.comparison_date
        THEN ps.total_orders ELSE 0
    END), 0) AS previous_orders,

    COALESCE(SUM(CASE
        WHEN ps.order_date = dp.report_date
        THEN ps.total_orders ELSE 0
    END), 0) AS current_orders,

    COALESCE(SUM(CASE
        WHEN ps.order_date = dp.comparison_date
        THEN ps.units_sold ELSE 0
    END), 0) AS previous_units,

    COALESCE(SUM(CASE
        WHEN ps.order_date = dp.report_date
        THEN ps.units_sold ELSE 0
    END), 0) AS current_units,

    ROUND(COALESCE(SUM(CASE
        WHEN ps.order_date = dp.comparison_date
        THEN ps.sales_after_discounts ELSE 0
    END), 0), 2) AS previous_sales,

    ROUND(COALESCE(SUM(CASE
        WHEN ps.order_date = dp.report_date
        THEN ps.sales_after_discounts ELSE 0
    END), 0), 2) AS current_sales

FROM product_summary ps
CROSS JOIN date_params dp
GROUP BY
    ps.product_id,
    ps.product_name,
    ps.category,
    dp.comparison_date,
    dp.report_date
ORDER BY
    current_sales - previous_sales ASC;