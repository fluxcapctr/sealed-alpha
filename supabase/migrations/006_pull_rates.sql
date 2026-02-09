-- Pull rates per rarity tier per set
-- Data sourced from TCGPlayer articles (via TCG in Figures)
CREATE TABLE pull_rates (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  set_id UUID REFERENCES sets(id),
  rarity TEXT NOT NULL,
  packs_per_hit NUMERIC NOT NULL,   -- "1 in X packs" → X
  cards_in_set INTEGER,             -- how many cards of this rarity in the set
  source TEXT DEFAULT 'TCGPlayer',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(set_id, rarity)
);

-- RLS: allow anonymous reads
ALTER TABLE pull_rates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous reads" ON pull_rates FOR SELECT USING (true);
