# Workflow: Scrape Prices

## Objective
Fetch current pricing data for all active sealed products and store snapshots in Supabase.

## When to Use
- Daily automated scrape (via `run_daily.py`)
- Manual re-scrape of specific products or sets
- After adding new products

## Required Inputs
- Supabase credentials configured in `.env`
- Products seeded in database (see `workflows/seed_products.md`)

## Tool to Run
```bash
python tools/scrape_prices.py
python tools/scrape_prices.py --product-id UUID
python tools/scrape_prices.py --set-id UUID
python tools/scrape_prices.py --dry-run
```

## Step-by-Step
1. Tool loads all active products (or filtered subset)
2. For each product, fetches current pricing from TCGPlayer
3. Extracts: market price, low/mid/high prices, listing count
4. Inserts a `PriceSnapshot` record (one per product per day)
5. Reports success/failure counts

## Data Extracted Per Product
- **Market Price**: Based on recent completed sales (most reliable)
- **Low Price**: Lowest current listing price
- **Mid Price**: Median listing price
- **High Price**: Highest listing price
- **Listed Median Price**: TCGPlayer's listed median
- **Direct Low Price**: TCGPlayer Direct lowest price
- **Total Listings**: Number of active seller listings

## Rate Limiting
- Randomized delay between requests (configurable, default 2-5s)
- Exponential backoff on failures (2s, 4s, 8s)
- User-agent rotation per request
- Maximum 3 retries per product before marking as failed

## Scheduling
- **New sets** (< 6 months): Scrape daily
- **Mid-age sets** (6 months - 2 years): Every other day
- **Old sets** (> 2 years): Weekly

## Edge Cases
- Products with no listings return null prices — store as NULL, don't skip
- TCGPlayer may rate-limit or block — exponential backoff handles this
- Market price may differ significantly from low price for low-volume products
- Some products may be temporarily unavailable — retry next run
- Duplicate snapshots for same day are handled by UPSERT on (product_id, snapshot_date)

## Output
- `price_snapshots` table updated with new daily snapshots
- Console output: `{success: N, failed: N, skipped: N}`
