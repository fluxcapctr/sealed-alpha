-- Migration 008: Add top card image URL to sets table
-- Stores the pokemontcg.io high-res image URL of the most expensive card per set
-- Used as background art on the sets page

ALTER TABLE sets ADD COLUMN top_card_image_url TEXT;
