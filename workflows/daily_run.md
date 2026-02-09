# Workflow: Daily Pipeline

## Objective
Execute the full daily data pipeline: scrape prices, scrape sales, compute signals, refresh analytics, check alerts.

## When to Use
- Automated daily run (via scheduler)
- Manual full pipeline execution

## Tool to Run
```bash
python tools/run_daily.py
python tools/run_daily.py --prices-only
python tools/run_daily.py --signals-only
```

## Pipeline Steps (in order)
1. **Scrape Prices** — Fetch current prices for all products due for scraping
2. **Scrape Sales** — Fetch sales volume data
3. **Compute Signals** — Run the signal engine on all products with sufficient history
4. **Refresh Analytics** — Refresh the `product_analytics` materialized view
5. **Check Alerts** — Compare new signals to previous, create alerts for threshold crossings
6. **Send Alerts** — Email alert digest if any new alerts were created

## Scrape Frequency (by set age)
| Set Age | Interval | Rationale |
|---------|----------|-----------|
| < 1 year | Daily | Active market, frequent price changes |
| 1-3 years | Every 3 days | Moderate movement, balance API usage |
| 3+ years | Weekly | Stable prices, minimal changes |

Configured in `config.py` (`schedule_new_days`, `schedule_mid_days`, `schedule_old_days`).

## Scheduling (Active)
**Windows Task Scheduler** — runs nightly at midnight.
- Task name: `PokemonScraperDaily`
- Wrapper: `tools/scheduled_run.bat`
- Logs to: `.tmp/scheduled_run.log`

To manage:
```bash
# Check status
schtasks /query /tn "PokemonScraperDaily" /fo LIST

# Disable
schtasks /change /tn "PokemonScraperDaily" /disable

# Re-enable
schtasks /change /tn "PokemonScraperDaily" /enable

# Delete
schtasks /delete /tn "PokemonScraperDaily" /f
```

## Expected Duration
- With ~500 products at 2-3 second delays: ~20-30 minutes
- Signal computation: ~1 minute
- Analytics refresh: ~5 seconds

## Error Handling
- Individual product scrape failures don't stop the pipeline
- Failed products are logged and retried next run
- Signal computation skips products with < 7 days of price history
- Pipeline logs full results to console and `.tmp/daily_run_log.json`

## Output
- Fresh price_snapshots for all due products
- Fresh sales_snapshots
- Updated signals for all products
- Refreshed product_analytics materialized view
- Alerts created and emailed (if applicable)
- Run log at `.tmp/daily_run_log.json`
