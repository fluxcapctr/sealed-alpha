-- Migration 005: Add total set value (complete master set) and card count to sets table

ALTER TABLE sets ADD COLUMN IF NOT EXISTS total_set_value NUMERIC(12,2);
ALTER TABLE sets ADD COLUMN IF NOT EXISTS total_cards INTEGER;
ALTER TABLE sets ADD COLUMN IF NOT EXISTS set_value_updated_at TIMESTAMPTZ;
