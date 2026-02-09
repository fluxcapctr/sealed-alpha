-- Pokemon Sealed Product Investment Tracker
-- Migration 001: Core tables

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- SETS
-- ============================================
CREATE TABLE sets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    code            TEXT UNIQUE,
    series          TEXT,
    release_date    DATE,
    tcgplayer_group_id INTEGER UNIQUE,
    set_url         TEXT,
    image_url       TEXT,
    is_in_print     BOOLEAN DEFAULT TRUE,
    is_in_rotation  BOOLEAN DEFAULT TRUE,
    total_products  INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- PRODUCTS
-- ============================================
CREATE TABLE products (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    set_id                  UUID REFERENCES sets(id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    product_type            TEXT NOT NULL CHECK (product_type IN (
        'Booster Box', 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box',
        'Booster Pack', 'Collection Box', 'Other'
    )),
    tcgplayer_product_id    INTEGER UNIQUE,
    tcgplayer_url           TEXT,
    image_url               TEXT,
    release_date            DATE,
    msrp                    NUMERIC(10,2),
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- PRICE SNAPSHOTS
-- ============================================
CREATE TABLE price_snapshots (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id          UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    market_price        NUMERIC(10,2),
    low_price           NUMERIC(10,2),
    mid_price           NUMERIC(10,2),
    high_price          NUMERIC(10,2),
    listed_median_price NUMERIC(10,2),
    direct_low_price    NUMERIC(10,2),
    total_listings      INTEGER,
    foil_price          NUMERIC(10,2),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, snapshot_date)
);

-- ============================================
-- SALES SNAPSHOTS
-- ============================================
CREATE TABLE sales_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    total_sales     INTEGER,
    avg_sale_price  NUMERIC(10,2),
    min_sale_price  NUMERIC(10,2),
    max_sale_price  NUMERIC(10,2),
    sale_count_24h  INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, snapshot_date)
);

-- ============================================
-- SIGNALS (computed buy/sell scores)
-- ============================================
CREATE TABLE signals (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id              UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    signal_date             DATE NOT NULL DEFAULT CURRENT_DATE,
    composite_score         NUMERIC(5,1),
    price_vs_ma_score       NUMERIC(5,1),
    momentum_score          NUMERIC(5,1),
    volatility_score        NUMERIC(5,1),
    listings_score          NUMERIC(5,1),
    sales_velocity_score    NUMERIC(5,1),
    lifecycle_score         NUMERIC(5,1),
    recommendation          TEXT CHECK (recommendation IN (
        'STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL'
    )),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, signal_date)
);

-- ============================================
-- ALERTS
-- ============================================
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id      UUID REFERENCES products(id) ON DELETE CASCADE,
    alert_type      TEXT NOT NULL CHECK (alert_type IN (
        'strong_buy', 'buy', 'sell', 'strong_sell',
        'price_drop', 'price_spike', 'new_low', 'volume_spike',
        'end_of_print'
    )),
    message         TEXT,
    signal_score    NUMERIC(5,1),
    is_sent         BOOLEAN DEFAULT FALSE,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- USER SETTINGS
-- ============================================
CREATE TABLE user_settings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email               TEXT,
    alert_threshold     NUMERIC(5,1) DEFAULT 50.0,
    alert_frequency     TEXT DEFAULT 'daily' CHECK (alert_frequency IN ('realtime', 'daily', 'weekly')),
    watched_product_ids UUID[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- UPDATED_AT TRIGGER
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_sets_updated_at
    BEFORE UPDATE ON sets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
