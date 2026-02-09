-- Pokemon Sealed Product Investment Tracker
-- Migration 003: Row Level Security policies

-- Enable RLS on all tables
ALTER TABLE sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Public read access (dashboard uses anon key)
CREATE POLICY "Public read: sets" ON sets FOR SELECT USING (true);
CREATE POLICY "Public read: products" ON products FOR SELECT USING (true);
CREATE POLICY "Public read: price_snapshots" ON price_snapshots FOR SELECT USING (true);
CREATE POLICY "Public read: sales_snapshots" ON sales_snapshots FOR SELECT USING (true);
CREATE POLICY "Public read: signals" ON signals FOR SELECT USING (true);
CREATE POLICY "Public read: alerts" ON alerts FOR SELECT USING (true);
CREATE POLICY "Public read: user_settings" ON user_settings FOR SELECT USING (true);

-- Writes are handled by Python tools using the service role key,
-- which bypasses RLS entirely. No INSERT/UPDATE/DELETE policies
-- are needed for the anon key.
