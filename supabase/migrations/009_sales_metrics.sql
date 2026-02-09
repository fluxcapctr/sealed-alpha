-- Migration 009: Add Booster Bundle type + sales metrics + view update
-- Source: TCGPlayer price history API (range=quarter)
-- Updated by: tools/scrape_sales_data.py

-- Add Booster Bundle to the product_type CHECK constraint
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_product_type_check;
ALTER TABLE products ADD CONSTRAINT products_product_type_check
  CHECK (product_type IN (
    'Booster Box', 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box',
    'Booster Pack', 'Booster Bundle', 'Collection Box', 'Other'
  ));

-- Add sales metrics columns
ALTER TABLE products
ADD COLUMN IF NOT EXISTS total_sold_90d       INTEGER,
ADD COLUMN IF NOT EXISTS avg_daily_sold       NUMERIC(10,2);

-- Update materialized view to expose these columns
DROP MATERIALIZED VIEW IF EXISTS product_analytics;

CREATE MATERIALIZED VIEW product_analytics AS
SELECT
    p.id AS product_id,
    p.name AS product_name,
    p.product_type,
    p.tcgplayer_product_id,
    p.tcgplayer_url,
    p.image_url,
    p.release_date::text AS release_date,
    p.msrp,

    s.id AS set_id,
    s.name AS set_name,
    s.series,
    s.is_in_print,
    s.is_in_rotation,
    s.total_set_value,

    -- Latest price data
    latest.market_price AS current_price,
    latest.low_price AS current_low_price,
    latest.total_listings AS current_listings,

    -- Latest quantity
    (SELECT ps.available_quantity
     FROM price_snapshots ps
     WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS current_quantity,

    -- Days since release
    CASE
        WHEN p.release_date IS NOT NULL
        THEN (CURRENT_DATE - p.release_date)
        ELSE NULL
    END AS days_since_release,

    -- Moving averages
    (SELECT AVG(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS ma_7d,

    (SELECT AVG(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS ma_30d,

    (SELECT AVG(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '90 days') AS ma_90d,

    -- Price 7 days ago
    (SELECT ps.market_price
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_7d_ago,

    -- Price 30 days ago
    (SELECT ps.market_price
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_30d_ago,

    -- Price 90 days ago
    (SELECT ps.market_price
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_90d_ago,

    -- 7-day price change %
    CASE
        WHEN (SELECT ps.market_price FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.market_price FROM price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            ((latest.market_price - (SELECT ps.market_price FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1))
            / (SELECT ps.market_price FROM price_snapshots ps
               WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS price_change_7d_pct,

    -- 30-day price change %
    CASE
        WHEN (SELECT ps.market_price FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.market_price FROM price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            ((latest.market_price - (SELECT ps.market_price FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1))
            / (SELECT ps.market_price FROM price_snapshots ps
               WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS price_change_30d_pct,

    -- Price volatility (stddev over 30 days)
    (SELECT STDDEV(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS volatility_30d,

    -- All-time low/high
    (SELECT MIN(ps.market_price) FROM price_snapshots ps WHERE ps.product_id = p.id) AS all_time_low,
    (SELECT MAX(ps.market_price) FROM price_snapshots ps WHERE ps.product_id = p.id) AS all_time_high,

    -- Listings 7 days ago (for trend)
    (SELECT ps.total_listings
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS listings_7d_ago,

    -- Sales velocity (avg daily sales last 7 days)
    (SELECT AVG(ss.sale_count_24h)
     FROM sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS avg_daily_sales_7d,

    -- Sales velocity (avg daily sales last 30 days)
    (SELECT AVG(ss.sale_count_24h)
     FROM sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS avg_daily_sales_30d,

    -- TCGPlayer sales metrics (from quarterly API)
    p.total_sold_90d,
    p.avg_daily_sold,

    -- Total data points
    (SELECT COUNT(*) FROM price_snapshots ps WHERE ps.product_id = p.id) AS total_price_points,

    -- Tracking range
    (SELECT MIN(ps.snapshot_date) FROM price_snapshots ps WHERE ps.product_id = p.id) AS first_tracked,
    (SELECT MAX(ps.snapshot_date) FROM price_snapshots ps WHERE ps.product_id = p.id) AS last_tracked,

    -- Latest signal
    sig.composite_score AS signal_score,
    sig.recommendation AS signal_recommendation

FROM products p
JOIN sets s ON p.set_id = s.id
LEFT JOIN LATERAL (
    SELECT ps.*
    FROM price_snapshots ps
    WHERE ps.product_id = p.id
    ORDER BY ps.snapshot_date DESC
    LIMIT 1
) latest ON TRUE
LEFT JOIN LATERAL (
    SELECT sg.*
    FROM signals sg
    WHERE sg.product_id = p.id
    ORDER BY sg.signal_date DESC
    LIMIT 1
) sig ON TRUE
WHERE p.is_active = TRUE;

-- Recreate unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_product_analytics_id ON product_analytics(product_id);

-- Recreate refresh function
CREATE OR REPLACE FUNCTION refresh_product_analytics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_analytics;
END;
$$ LANGUAGE plpgsql;
