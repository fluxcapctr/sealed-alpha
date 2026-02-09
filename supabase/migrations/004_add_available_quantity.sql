-- Pokemon Sealed Product Investment Tracker
-- Migration 004: Add available_quantity to price_snapshots
-- Tracks the total units available across all sellers (from TCGPlayer listings API)

-- Add available_quantity column
ALTER TABLE price_snapshots ADD COLUMN available_quantity INTEGER;

-- Drop and recreate the materialized view with quantity columns
DROP MATERIALIZED VIEW IF EXISTS product_analytics;

CREATE MATERIALIZED VIEW product_analytics AS
SELECT
    p.id AS product_id,
    p.name AS product_name,
    p.product_type,
    p.tcgplayer_product_id,
    p.tcgplayer_url,
    p.image_url AS product_image,
    p.msrp,

    -- Set info
    s.id AS set_id,
    s.name AS set_name,
    s.code AS set_code,
    s.series,
    s.release_date,
    s.is_in_print,
    s.is_in_rotation,

    -- Days since release
    EXTRACT(DAY FROM NOW() - s.release_date::timestamp)::integer AS days_since_release,

    -- Latest price data
    latest.market_price AS current_price,
    latest.low_price AS current_low,
    latest.mid_price AS current_mid,
    latest.high_price AS current_high,
    latest.total_listings AS current_listings,
    latest.available_quantity AS current_quantity,
    latest.snapshot_date AS last_price_date,

    -- 7-day moving average
    (SELECT AVG(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS ma_7d,

    -- 30-day moving average
    (SELECT AVG(ps.market_price)
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS ma_30d,

    -- 90-day moving average
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

    -- Quantity 7 days ago
    (SELECT ps.available_quantity
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_7d_ago,

    -- Quantity 30 days ago
    (SELECT ps.available_quantity
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_30d_ago,

    -- Quantity 90 days ago
    (SELECT ps.available_quantity
     FROM price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_90d_ago,

    -- Quantity velocity: % change over 90 days (negative = units selling)
    CASE
        WHEN (SELECT ps.available_quantity FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.available_quantity FROM price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            ((latest.available_quantity - (SELECT ps.available_quantity FROM price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1))::numeric
            / (SELECT ps.available_quantity FROM price_snapshots ps
               WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS quantity_change_90d_pct,

    -- Sales velocity (avg daily sales last 7 days — from sales_snapshots if populated)
    (SELECT AVG(ss.sale_count_24h)
     FROM sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS avg_daily_sales_7d,

    -- Sales velocity (avg daily sales last 30 days)
    (SELECT AVG(ss.sale_count_24h)
     FROM sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS avg_daily_sales_30d,

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

-- Unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_product_analytics_id ON product_analytics(product_id);

-- Recreate the refresh function
CREATE OR REPLACE FUNCTION refresh_product_analytics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_analytics;
END;
$$ LANGUAGE plpgsql;
