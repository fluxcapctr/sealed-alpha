-- Migration 010b: Recreate product_analytics view with language column
-- Run this in Supabase SQL Editor
-- (The DROP already ran successfully, so we just need the CREATE)

-- First verify tables exist
-- SELECT count(*) FROM public.sets;
-- SELECT count(*) FROM public.products;

CREATE MATERIALIZED VIEW public.product_analytics AS
SELECT
    p.id AS product_id,
    p.name AS product_name,
    p.product_type,
    p.tcgplayer_product_id,
    p.tcgplayer_url,
    p.image_url AS product_image,
    p.msrp,

    s.id AS set_id,
    s.name AS set_name,
    s.code AS set_code,
    s.series,
    p.release_date::text AS release_date,
    s.is_in_print,
    s.is_in_rotation,

    -- Language
    s.language AS language,

    -- Days since release
    CASE
        WHEN p.release_date IS NOT NULL
        THEN (CURRENT_DATE - p.release_date)
        ELSE NULL
    END AS days_since_release,

    -- Latest price data
    latest.market_price AS current_price,
    latest.low_price AS current_low,
    latest.mid_price AS current_mid,
    latest.high_price AS current_high,
    latest.total_listings AS current_listings,

    -- Latest quantity
    (SELECT ps.available_quantity
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS current_quantity,

    -- Latest price date
    latest.snapshot_date AS last_price_date,

    -- Moving averages
    (SELECT AVG(ps.market_price)
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS ma_7d,

    (SELECT AVG(ps.market_price)
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS ma_30d,

    (SELECT AVG(ps.market_price)
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '90 days') AS ma_90d,

    -- Price N days ago
    (SELECT ps.market_price
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_7d_ago,

    (SELECT ps.market_price
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_30d_ago,

    (SELECT ps.market_price
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS price_90d_ago,

    -- 7-day price change %
    CASE
        WHEN (SELECT ps.market_price FROM public.price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.market_price FROM public.price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            ((latest.market_price - (SELECT ps.market_price FROM public.price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1))
            / (SELECT ps.market_price FROM public.price_snapshots ps
               WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS price_change_7d_pct,

    -- 30-day price change %
    CASE
        WHEN (SELECT ps.market_price FROM public.price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.market_price FROM public.price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            ((latest.market_price - (SELECT ps.market_price FROM public.price_snapshots ps
              WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1))
            / (SELECT ps.market_price FROM public.price_snapshots ps
               WHERE ps.product_id = p.id AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS price_change_30d_pct,

    -- Price volatility (stddev over 30 days)
    (SELECT STDDEV(ps.market_price)
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS volatility_30d,

    -- All-time low/high
    (SELECT MIN(ps.market_price) FROM public.price_snapshots ps WHERE ps.product_id = p.id) AS all_time_low,
    (SELECT MAX(ps.market_price) FROM public.price_snapshots ps WHERE ps.product_id = p.id) AS all_time_high,

    -- Listings 7 days ago
    (SELECT ps.total_listings
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS listings_7d_ago,

    -- Quantity N days ago
    (SELECT ps.available_quantity
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.available_quantity IS NOT NULL
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_7d_ago,

    (SELECT ps.available_quantity
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.available_quantity IS NOT NULL
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '30 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_30d_ago,

    (SELECT ps.available_quantity
     FROM public.price_snapshots ps
     WHERE ps.product_id = p.id
       AND ps.available_quantity IS NOT NULL
       AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
     ORDER BY ps.snapshot_date DESC LIMIT 1) AS quantity_90d_ago,

    -- Quantity change 90d %
    CASE
        WHEN (SELECT ps.available_quantity FROM public.price_snapshots ps
              WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
              AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
              ORDER BY ps.snapshot_date DESC LIMIT 1) IS NOT NULL
             AND (SELECT ps.available_quantity FROM public.price_snapshots ps
                  WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
                  AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
                  ORDER BY ps.snapshot_date DESC LIMIT 1) > 0
        THEN ROUND(
            (((SELECT ps.available_quantity FROM public.price_snapshots ps
               WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
               ORDER BY ps.snapshot_date DESC LIMIT 1)
              - (SELECT ps.available_quantity FROM public.price_snapshots ps
                 WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
                 AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
                 ORDER BY ps.snapshot_date DESC LIMIT 1))::numeric
            / (SELECT ps.available_quantity FROM public.price_snapshots ps
               WHERE ps.product_id = p.id AND ps.available_quantity IS NOT NULL
               AND ps.snapshot_date <= CURRENT_DATE - INTERVAL '90 days'
               ORDER BY ps.snapshot_date DESC LIMIT 1) * 100)::numeric, 2)
        ELSE NULL
    END AS quantity_change_90d_pct,

    -- Sales velocity from sales_snapshots
    (SELECT AVG(ss.sale_count_24h)
     FROM public.sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '7 days') AS avg_daily_sales_7d,

    (SELECT AVG(ss.sale_count_24h)
     FROM public.sales_snapshots ss
     WHERE ss.product_id = p.id
       AND ss.snapshot_date >= CURRENT_DATE - INTERVAL '30 days') AS avg_daily_sales_30d,

    -- TCGPlayer 90-day sales metrics (from products table)
    p.total_sold_90d,
    p.avg_daily_sold,

    -- Total data points
    (SELECT COUNT(*) FROM public.price_snapshots ps WHERE ps.product_id = p.id) AS total_price_points,

    -- Tracking range
    (SELECT MIN(ps.snapshot_date) FROM public.price_snapshots ps WHERE ps.product_id = p.id) AS first_tracked,
    (SELECT MAX(ps.snapshot_date) FROM public.price_snapshots ps WHERE ps.product_id = p.id) AS last_tracked,

    -- Latest signal
    sig.composite_score AS signal_score,
    sig.recommendation AS signal_recommendation

FROM public.products p
JOIN public.sets s ON p.set_id = s.id
LEFT JOIN LATERAL (
    SELECT ps.*
    FROM public.price_snapshots ps
    WHERE ps.product_id = p.id
    ORDER BY ps.snapshot_date DESC
    LIMIT 1
) latest ON TRUE
LEFT JOIN LATERAL (
    SELECT sg.*
    FROM public.signals sg
    WHERE sg.product_id = p.id
    ORDER BY sg.signal_date DESC
    LIMIT 1
) sig ON TRUE
WHERE p.is_active = TRUE;

-- Recreate unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_product_analytics_id ON public.product_analytics(product_id);

-- Grant read access to anon role (needed for dashboard)
GRANT SELECT ON public.product_analytics TO anon;
GRANT SELECT ON public.product_analytics TO authenticated;

-- Recreate refresh function
CREATE OR REPLACE FUNCTION public.refresh_product_analytics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.product_analytics;
END;
$$ LANGUAGE plpgsql;
