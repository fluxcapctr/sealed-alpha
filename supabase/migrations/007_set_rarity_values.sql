-- Per-rarity value breakdown for each set
-- Used to compute Box EV / Rip Score
CREATE TABLE set_rarity_values (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  set_id UUID REFERENCES sets(id),
  rarity TEXT NOT NULL,
  total_value NUMERIC NOT NULL,     -- sum of all card market prices in this rarity tier
  card_count INTEGER NOT NULL,      -- number of unique cards in this rarity tier
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(set_id, rarity)
);

-- RLS: allow anonymous reads
ALTER TABLE set_rarity_values ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous reads" ON set_rarity_values FOR SELECT USING (true);
