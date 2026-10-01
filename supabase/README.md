# supabase/

SQL migrations for the Sealed Alpha database (Supabase / Postgres).

## How migrations are applied (important)

Files in `migrations/` are applied **by hand**: open the Supabase dashboard,
paste a file into the SQL editor, run it. There is **no migration tracking** (the
Supabase CLI's `schema_migrations` table is not used), so nothing records which
files the live database has had. The live database can therefore differ from the
files; every statement in new migrations must be idempotent and must check what
exists before changing it. The SQL editor runs a pasted script as one transaction:
an error rolls the whole script back.

## Order

Apply in **byte order** (C locale), which is *not* what a locale-aware `ls` or
editor sort always shows (it can put `009b` before `009_`):

```
001_initial_schema.sql
002_indexes_and_views.sql
003_rls_policies.sql
004_add_available_quantity.sql
005_add_set_value.sql
006_pull_rates.sql
007_set_rarity_values.sql
008_top_card_image.sql
009_sales_metrics.sql        <- before 009b
009b_fix_view.sql
010_add_language.sql         <- before 010b
010b_recreate_view.sql
011_set_scores.sql
012_drip_campaign.sql
013_security_and_drift_fixes.sql
```

A clean empty database replays 001 -> 013 with no errors, and the whole sequence
can be replayed a second time on top (it converges to the same schema and
privileges). Older files were made re-runnable with mechanical `IF NOT EXISTS` /
`DROP ... IF EXISTS` edits; 012 keeps its original (insecure) policies and 013
corrects them, so never apply 012 on its own to a database that has 013.

## Rule: re-grant after every `product_analytics` recreate

`DROP MATERIALIZED VIEW product_analytics` + `CREATE` discards the view's grants
and its unique index. After **every** recreate (any file that does this):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_analytics_id ON public.product_analytics (product_id);
GRANT SELECT ON public.product_analytics TO anon, authenticated, service_role;
```

(The unique index is required by `REFRESH ... CONCURRENTLY`; the grant is what
lets the dashboard read the view.) 010b and 013 do this; 013 re-asserts both.

## Access model

- Dashboard (anon / authenticated keys): **read-only** on `sets`, `products`,
  `price_snapshots`, `sales_snapshots`, `signals`, `alerts`, `pull_rates`,
  `set_rarity_values`, `set_scores` and the `product_analytics` view.
- `drip_subscribers`, `drip_log`, `user_settings`: **service_role only**
  (no privileges and no policy for anon/authenticated).
- `refresh_product_analytics()`: callable by `service_role` only.
- All writes come from the Python tools and the Next.js API routes using the
  service-role key.

## Applying 013 safely

1. **Back up** first (Dashboard -> Database -> Backups, or `pg_dump`). 013 deletes
   duplicate `alerts` rows and rewrites some `drip_subscribers` e-mails/tokens.
2. Don't run it while the daily pipeline is running (it briefly locks `alerts`,
   and fails fast after 30 s instead of queueing if it can't get a lock).
3. Optional pre-flight look at the live state:
   ```sql
   select tablename, policyname, roles from pg_policies where tablename in ('drip_subscribers','drip_log','user_settings');
   select column_name from information_schema.columns where table_name = 'set_scores' order by 1;
   select lower(btrim(email)), count(*) from drip_subscribers group by 1 having count(*) > 1;
   select product_id, alert_type, created_at::date, count(*) from alerts group by 1,2,3 having count(*) > 1;
   ```
4. Paste `013_security_and_drift_fixes.sql` into the SQL editor and run it. It is
   idempotent; if it errors nothing is applied, fix and re-run.
5. **Read the messages.** A `WARNING` means a step was skipped or relaxed instead
   of failing:
   - *"differ only by e-mail case/whitespace"*: duplicate subscribers exist, so
     the case-insensitive unique index was **not** created and nobody was
     deleted. Merge/delete the duplicates by hand (query is in the message) and
     re-run 013.
   - *"CHECK added NOT VALID"*: existing rows violate a new CHECK; new writes are
     still checked. Fix the rows, then `ALTER TABLE ... VALIDATE CONSTRAINT ...`.
6. Run `select public.refresh_product_analytics();` once so the view picks up the
   backfilled `products.release_date` (lifecycle score input).
7. Check from outside: with only the anon key, `GET /rest/v1/drip_subscribers`
   must return a permission error and `GET /rest/v1/product_analytics?limit=1`
   must still return data.
8. Deploy the Python/dashboard changes that go with it: the pipeline now
   skips alerts already raised today before inserting (a same-day duplicate that
   slips through a race fails with 23505 and is ignored), and the sign-up route
   trims and lowercases e-mails before looking them up.

## Housekeeping

`supabase/.temp/` is Supabase CLI cache and is git-ignored via `supabase/.gitignore`.
It was committed earlier; untrack it once with `git rm -r --cached supabase/.temp`.
