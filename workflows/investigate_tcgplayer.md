# Workflow: Investigate TCGPlayer APIs

## Objective
Discover TCGPlayer's internal API endpoints for pricing and product data to determine the best scraping strategy.

## When to Use
- Initial project setup (run once)
- When scraping breaks (TCGPlayer may have changed their API)
- When adding new data types to scrape

## Required Inputs
- **URL** (optional): A specific TCGPlayer product URL to investigate
- **Search term** (optional): A search query to investigate the search API

## Tool to Run
```bash
python tools/investigate_tcgplayer.py
python tools/investigate_tcgplayer.py --url "https://www.tcgplayer.com/product/556996/..."
python tools/investigate_tcgplayer.py --search "pokemon booster box"
python tools/investigate_tcgplayer.py --all
```

## Step-by-Step
1. Run the investigation tool with `--all` flag for first-time discovery
2. Review the captured API endpoints in `.tmp/tcgplayer_api_map.json`
3. For each endpoint, note:
   - URL pattern
   - Required headers (especially auth tokens, bearer tokens)
   - Request body format (for POST endpoints)
   - Response format and key fields
4. Update `config.py` with discovered base URLs
5. Update this workflow's "Known Endpoints" section with findings

## Priority Order for Scraping Strategy
1. **Internal JSON APIs** (fastest, most reliable) — direct HTTP requests
2. **Playwright page scraping** (fallback) — full browser rendering

## Known Endpoints (update after investigation)
- `mp-search-api.tcgplayer.com/v1/search/request` — Product search (POST)
- `mpapi.tcgplayer.com/v2/product/*/pricepoints` — Price data
- `infinite-api.tcgplayer.com` — May have additional endpoints

## Edge Cases
- TCGPlayer may use bearer tokens that expire — check `Authorization` headers
- Rate limiting is likely — start conservative (2-5s between requests)
- Some endpoints may require cookies from an active browser session
- Search API may use pagination tokens for multi-page results
- Category/group IDs may change between API versions

## Output
- `.tmp/tcgplayer_api_map.json` — Full investigation results with all captured API calls
