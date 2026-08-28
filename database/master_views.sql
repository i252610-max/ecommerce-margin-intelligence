-- =====================================================
-- MASTER ANALYTICAL VIEWS
-- Reproducible data model for competitor intelligence
-- =====================================================

-- ---------- Bridge table (empty for now) ----------
CREATE TABLE IF NOT EXISTS product_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_product_id TEXT,
    competitor TEXT,
    competitor_product_name TEXT,
    match_score REAL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

-- ---------- View 1: Latest Competitor Prices ----------
DROP VIEW IF EXISTS v_latest_competitor_prices;
CREATE VIEW v_latest_competitor_prices AS
WITH ranked AS (
    SELECT
        competitor,
        product_name,
        price,
        scraped_at,
        ROW_NUMBER() OVER (
            PARTITION BY competitor, product_name
            ORDER BY scraped_at DESC
        ) AS rn
    FROM price_history
)
SELECT
    competitor,
    product_name,
    price AS latest_price,
    scraped_at AS last_seen_at
FROM ranked
WHERE rn = 1;

-- ---------- View 2: 30-Day Competitor Trends ----------
DROP VIEW IF EXISTS v_competitor_trends_30d;
CREATE VIEW v_competitor_trends_30d AS
WITH max_date AS (
    SELECT MAX(scraped_at) AS max_scraped_at
    FROM price_history
),
windowed AS (
    SELECT
        competitor,
        product_name,
        price,
        scraped_at
    FROM price_history
    WHERE scraped_at >= date((SELECT max_scraped_at FROM max_date), '-30 days')
),
first_price AS (
    SELECT
        competitor,
        product_name,
        price AS first_price,
        ROW_NUMBER() OVER (
            PARTITION BY competitor, product_name
            ORDER BY scraped_at ASC
        ) AS rn
    FROM windowed
),
latest_price AS (
    SELECT
        competitor,
        product_name,
        price AS latest_price,
        ROW_NUMBER() OVER (
            PARTITION BY competitor, product_name
            ORDER BY scraped_at DESC
        ) AS rn
    FROM windowed
),
aggregated AS (
    SELECT
        competitor,
        product_name,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        AVG(price) AS avg_price,
        COUNT(*) AS observation_count
    FROM windowed
    GROUP BY competitor, product_name
)
SELECT
    a.competitor,
    a.product_name,
    a.min_price,
    a.max_price,
    a.avg_price,
    a.observation_count,
    fp.first_price,
    lp.latest_price,
    CASE
        WHEN fp.first_price = 0 THEN 0
        ELSE ROUND((lp.latest_price - fp.first_price) * 100.0 / fp.first_price, 2)
    END AS price_change_pct
FROM aggregated a
JOIN (SELECT competitor, product_name, first_price FROM first_price WHERE rn = 1) fp
    ON a.competitor = fp.competitor AND a.product_name = fp.product_name
JOIN (SELECT competitor, product_name, latest_price FROM latest_price WHERE rn = 1) lp
    ON a.competitor = lp.competitor AND a.product_name = lp.product_name;

-- ---------- View 3: Master Intelligence ----------
DROP VIEW IF EXISTS v_master_intelligence;
CREATE VIEW v_master_intelligence AS
SELECT
    lp.competitor,
    lp.product_name AS competitor_product_name,
    lp.latest_price,
    lp.last_seen_at,
    tr.min_price,
    tr.max_price,
    tr.avg_price,
    tr.observation_count,
    tr.price_change_pct,
    pm.internal_product_id,
    pp.product_name AS internal_product_name,
    pp.total_units,
    pp.total_revenue,
    pp.total_cost,
    pp.total_profit,
    pp.unit_cost,
    pp.gross_margin_pct
FROM v_latest_competitor_prices lp
LEFT JOIN v_competitor_trends_30d tr
    ON lp.competitor = tr.competitor AND lp.product_name = tr.product_name
LEFT JOIN product_matches pm
    ON lp.competitor = pm.competitor AND lp.product_name = pm.competitor_product_name
LEFT JOIN product_profitability pp
    ON pm.internal_product_id = pp.product_id;