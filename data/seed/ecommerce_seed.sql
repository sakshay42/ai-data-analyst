-- =============================================================================
-- E-Commerce Seed Data for AI Data Analyst Project
-- PostgreSQL seed script with ~500 customers, ~200 products, ~5000 orders,
-- ~15000 order_items, and ~2000 reviews spanning 2024-01 through 2025-12.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. Clean slate
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS reviews      CASCADE;
DROP TABLE IF EXISTS order_items  CASCADE;
DROP TABLE IF EXISTS orders       CASCADE;
DROP TABLE IF EXISTS products     CASCADE;
DROP TABLE IF EXISTS customers    CASCADE;

-- ---------------------------------------------------------------------------
-- 1. customers  (~500 rows)
-- ---------------------------------------------------------------------------
CREATE TABLE customers (
    customer_id   SERIAL PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    city          VARCHAR(60)  NOT NULL,
    state         VARCHAR(2)   NOT NULL,
    signup_date   DATE         NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_customers_signup_date ON customers (signup_date);
CREATE INDEX idx_customers_state       ON customers (state);

INSERT INTO customers (first_name, last_name, email, city, state, signup_date, is_active)
SELECT
    -- Rotate through 20 first names
    (ARRAY['James','Mary','Robert','Patricia','John','Jennifer','Michael',
           'Linda','David','Elizabeth','William','Barbara','Richard','Susan',
           'Joseph','Jessica','Thomas','Sarah','Charles','Karen'])
        [1 + (g % 20)],
    -- Rotate through 25 last names
    (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller',
           'Davis','Rodriguez','Martinez','Hernandez','Lopez','Gonzalez',
           'Wilson','Anderson','Thomas','Taylor','Moore','Jackson','Martin',
           'Lee','Perez','Thompson','White','Harris'])
        [1 + (g % 25)],
    'customer_' || g || '@example.com',
    -- 15 cities
    (ARRAY['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia',
           'San Antonio','San Diego','Dallas','San Jose','Austin','Jacksonville',
           'Fort Worth','Columbus','Charlotte'])
        [1 + (g % 15)],
    -- 10 states
    (ARRAY['NY','CA','IL','TX','AZ','PA','TX','CA','TX','CA'])
        [1 + (g % 10)],
    -- Spread signups across 2023-06 to 2025-06
    '2023-06-01'::date + (random() * 730)::int,
    -- 92% active
    random() > 0.08
FROM generate_series(1, 500) AS g;

-- ---------------------------------------------------------------------------
-- 2. products  (~200 rows)
-- ---------------------------------------------------------------------------
CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    product_name  VARCHAR(150) NOT NULL,
    category      VARCHAR(40)  NOT NULL,
    subcategory   VARCHAR(60)  NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    cost_price    NUMERIC(10,2) NOT NULL CHECK (cost_price > 0),
    stock_qty     INT          NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    is_available  BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_products_category ON products (category);

-- Electronics (50 products)
INSERT INTO products (product_name, category, subcategory, unit_price, cost_price, stock_qty, is_available)
SELECT
    (ARRAY['Wireless Headphones','Bluetooth Speaker','USB-C Hub','Laptop Stand',
           'Mechanical Keyboard','Gaming Mouse','Webcam HD','Portable Charger',
           'Smart Watch','Tablet Case'])
        [1 + (g % 10)]
    || ' Model-' || g,
    'Electronics',
    (ARRAY['Audio','Accessories','Peripherals','Wearables','Storage'])
        [1 + (g % 5)],
    -- Price between 19.99 and 499.99
    round((19.99 + random() * 480)::numeric, 2),
    -- Cost is 40-70% of a midrange price
    round((10 + random() * 200)::numeric, 2),
    (50 + (random() * 450)::int),
    random() > 0.05
FROM generate_series(1, 50) AS g;

-- Clothing (50 products)
INSERT INTO products (product_name, category, subcategory, unit_price, cost_price, stock_qty, is_available)
SELECT
    (ARRAY['Cotton T-Shirt','Denim Jeans','Running Shoes','Winter Jacket',
           'Wool Sweater','Casual Shorts','Silk Scarf','Leather Belt',
           'Athletic Socks','Baseball Cap'])
        [1 + (g % 10)]
    || ' Style-' || g,
    'Clothing',
    (ARRAY['Tops','Bottoms','Footwear','Outerwear','Accessories'])
        [1 + (g % 5)],
    round((9.99 + random() * 190)::numeric, 2),
    round((4 + random() * 80)::numeric, 2),
    (30 + (random() * 300)::int),
    random() > 0.05
FROM generate_series(1, 50) AS g;

-- Home & Garden (40 products)
INSERT INTO products (product_name, category, subcategory, unit_price, cost_price, stock_qty, is_available)
SELECT
    (ARRAY['Ceramic Planter','LED Desk Lamp','Throw Pillow','Wall Clock',
           'Scented Candle','Kitchen Scale','Cutting Board','Door Mat',
           'Garden Hose','Bird Feeder'])
        [1 + (g % 10)]
    || ' Edition-' || g,
    'Home & Garden',
    (ARRAY['Decor','Lighting','Kitchen','Garden','Storage'])
        [1 + (g % 5)],
    round((7.99 + random() * 150)::numeric, 2),
    round((3 + random() * 60)::numeric, 2),
    (40 + (random() * 350)::int),
    random() > 0.05
FROM generate_series(1, 40) AS g;

-- Books (30 products)
INSERT INTO products (product_name, category, subcategory, unit_price, cost_price, stock_qty, is_available)
SELECT
    (ARRAY['Python Mastery','Data Science Handbook','Machine Learning Guide',
           'SQL Deep Dive','Cloud Architecture','DevOps Practices',
           'AI Ethics','Statistics Primer','Web Development','Algorithms 101'])
        [1 + (g % 10)]
    || ' Vol.' || g,
    'Books',
    (ARRAY['Programming','Data Science','Cloud','DevOps','General'])
        [1 + (g % 5)],
    round((12.99 + random() * 47)::numeric, 2),
    round((5 + random() * 20)::numeric, 2),
    (100 + (random() * 500)::int),
    random() > 0.03
FROM generate_series(1, 30) AS g;

-- Sports (30 products)
INSERT INTO products (product_name, category, subcategory, unit_price, cost_price, stock_qty, is_available)
SELECT
    (ARRAY['Yoga Mat','Resistance Bands','Dumbbell Set','Jump Rope',
           'Water Bottle','Fitness Tracker','Tennis Racket','Cycling Gloves',
           'Foam Roller','Gym Bag'])
        [1 + (g % 10)]
    || ' Pro-' || g,
    'Sports',
    (ARRAY['Fitness','Cardio','Strength','Outdoor','Accessories'])
        [1 + (g % 5)],
    round((9.99 + random() * 190)::numeric, 2),
    round((4 + random() * 80)::numeric, 2),
    (60 + (random() * 400)::int),
    random() > 0.05
FROM generate_series(1, 30) AS g;

-- ---------------------------------------------------------------------------
-- 3. orders  (~5000 rows)
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INT          NOT NULL REFERENCES customers (customer_id),
    order_date    TIMESTAMP    NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'completed'
                      CHECK (status IN ('pending','processing','shipped','completed','cancelled','refunded')),
    shipping_cost NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (shipping_cost >= 0),
    total_amount  NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE INDEX idx_orders_customer_id ON orders (customer_id);
CREATE INDEX idx_orders_order_date  ON orders (order_date);
CREATE INDEX idx_orders_status      ON orders (status);

INSERT INTO orders (customer_id, order_date, status, shipping_cost)
SELECT
    -- Random customer 1-500
    1 + (random() * 499)::int,
    -- Spread across 2024-01-01 to 2025-12-31 with random time of day
    '2024-01-01 00:00:00'::timestamp
        + ((random() * 730)::int || ' days')::interval
        + ((random() * 86400)::int || ' seconds')::interval,
    -- Weighted status distribution
    (CASE
        WHEN r < 0.72 THEN 'completed'
        WHEN r < 0.82 THEN 'shipped'
        WHEN r < 0.88 THEN 'processing'
        WHEN r < 0.93 THEN 'pending'
        WHEN r < 0.97 THEN 'cancelled'
        ELSE 'refunded'
    END),
    -- Shipping cost 0-15 with free shipping for some
    CASE WHEN random() < 0.3 THEN 0
         ELSE round((4.99 + random() * 10)::numeric, 2)
    END
FROM (
    SELECT g, random() AS r
    FROM generate_series(1, 5000) AS g
) sub;

-- ---------------------------------------------------------------------------
-- 4. order_items  (~15000 rows, ~3 items per order on average)
-- ---------------------------------------------------------------------------
CREATE TABLE order_items (
    item_id      SERIAL PRIMARY KEY,
    order_id     INT          NOT NULL REFERENCES orders (order_id),
    product_id   INT          NOT NULL REFERENCES products (product_id),
    quantity     INT          NOT NULL CHECK (quantity > 0),
    unit_price   NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 100)
);

CREATE INDEX idx_order_items_order_id   ON order_items (order_id);
CREATE INDEX idx_order_items_product_id ON order_items (product_id);

-- Generate ~15000 items by assigning 1-5 items per order
-- We use a CTE to expand each order into a random number of line items.
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct)
SELECT
    o.order_id,
    -- Random product 1-200
    1 + (random() * 199)::int,
    -- Quantity 1-4 (weighted toward 1)
    CASE
        WHEN random() < 0.55 THEN 1
        WHEN random() < 0.80 THEN 2
        WHEN random() < 0.95 THEN 3
        ELSE 4
    END,
    -- Snapshot price from products with slight random variation (+/- 5%)
    round((p_price * (0.95 + random() * 0.10))::numeric, 2),
    -- Discount: 70% no discount, 20% small, 10% larger
    CASE
        WHEN random() < 0.70 THEN 0
        WHEN random() < 0.90 THEN round((5 + random() * 10)::numeric, 2)
        ELSE round((15 + random() * 20)::numeric, 2)
    END
FROM orders o
CROSS JOIN LATERAL (
    -- Each order gets 1-5 line items (avg ~3)
    SELECT generate_series(1,
        CASE
            WHEN random() < 0.10 THEN 1
            WHEN random() < 0.35 THEN 2
            WHEN random() < 0.65 THEN 3
            WHEN random() < 0.85 THEN 4
            ELSE 5
        END
    ) AS item_num
) items
CROSS JOIN LATERAL (
    -- Grab a representative price to use (mid-range for the random product)
    SELECT round((20 + random() * 200)::numeric, 2) AS p_price
) price_gen;

-- ---------------------------------------------------------------------------
-- 5. Update orders.total_amount from line items
-- ---------------------------------------------------------------------------
UPDATE orders o
SET total_amount = sub.calc_total + o.shipping_cost
FROM (
    SELECT
        order_id,
        round(SUM(quantity * unit_price * (1 - discount_pct / 100.0))::numeric, 2) AS calc_total
    FROM order_items
    GROUP BY order_id
) sub
WHERE o.order_id = sub.order_id;

-- ---------------------------------------------------------------------------
-- 6. reviews  (~2000 rows)
-- ---------------------------------------------------------------------------
CREATE TABLE reviews (
    review_id    SERIAL PRIMARY KEY,
    product_id   INT          NOT NULL REFERENCES products (product_id),
    customer_id  INT          NOT NULL REFERENCES customers (customer_id),
    rating       SMALLINT     NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_title VARCHAR(200),
    review_text  TEXT,
    review_date  DATE         NOT NULL,
    verified     BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_reviews_product_id  ON reviews (product_id);
CREATE INDEX idx_reviews_customer_id ON reviews (customer_id);
CREATE INDEX idx_reviews_rating      ON reviews (rating);
CREATE INDEX idx_reviews_review_date ON reviews (review_date);

INSERT INTO reviews (product_id, customer_id, rating, review_title, review_text, review_date, verified)
SELECT
    -- Random product 1-200
    1 + (random() * 199)::int,
    -- Random customer 1-500
    1 + (random() * 499)::int,
    -- Weighted ratings: skewed toward 4-5 (realistic)
    CASE
        WHEN r < 0.05 THEN 1
        WHEN r < 0.12 THEN 2
        WHEN r < 0.25 THEN 3
        WHEN r < 0.55 THEN 4
        ELSE 5
    END,
    -- Review titles based on rating band
    CASE
        WHEN r < 0.12 THEN (ARRAY['Disappointing','Not worth it','Poor quality',
                                    'Would not recommend','Below expectations'])
                                [1 + (g % 5)]
        WHEN r < 0.25 THEN (ARRAY['It is okay','Average product','Decent enough',
                                    'Nothing special','Fair for the price'])
                                [1 + (g % 5)]
        WHEN r < 0.55 THEN (ARRAY['Good product','Happy with purchase','Solid choice',
                                    'Works well','Recommended'])
                                [1 + (g % 5)]
        ELSE (ARRAY['Excellent!','Absolutely love it','Best purchase ever',
                     'Highly recommended','Outstanding quality'])
                  [1 + (g % 5)]
    END,
    -- Review body text
    CASE
        WHEN r < 0.12 THEN 'This product did not meet my expectations. The quality was below what I hoped for given the price point.'
        WHEN r < 0.25 THEN 'The product is acceptable but nothing extraordinary. It does the job but there is room for improvement.'
        WHEN r < 0.55 THEN 'I am satisfied with this purchase. Good value for money and the product works as described.'
        ELSE 'Fantastic product! Exceeded all my expectations. Build quality is superb and it arrived quickly.'
    END,
    -- Review dates spread across 2024-02 to 2025-12 (slightly after orders start)
    '2024-02-01'::date + (random() * 700)::int,
    -- 65% verified purchases
    random() < 0.65
FROM (
    SELECT g, random() AS r
    FROM generate_series(1, 2000) AS g
) sub;

-- ---------------------------------------------------------------------------
-- 7. Summary statistics (verify counts)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    c_count INT; p_count INT; o_count INT; oi_count INT; r_count INT;
BEGIN
    SELECT count(*) INTO c_count  FROM customers;
    SELECT count(*) INTO p_count  FROM products;
    SELECT count(*) INTO o_count  FROM orders;
    SELECT count(*) INTO oi_count FROM order_items;
    SELECT count(*) INTO r_count  FROM reviews;

    RAISE NOTICE '--- Seed Summary ---';
    RAISE NOTICE 'Customers:   %', c_count;
    RAISE NOTICE 'Products:    %', p_count;
    RAISE NOTICE 'Orders:      %', o_count;
    RAISE NOTICE 'Order Items: %', oi_count;
    RAISE NOTICE 'Reviews:     %', r_count;
    RAISE NOTICE '--------------------';
END $$;
