-- Migration 013: security hardening, schema-drift fixes, alert dedupe, lifecycle data
--
-- Run in the Supabase SQL Editor (the editor runs the whole script as ONE
-- transaction: any error rolls everything back). Idempotent: safe to run again.
-- The live schema was built by hand-pasting 001..012, so every step below checks
-- what exists before changing it and uses DO blocks / IF [NOT] EXISTS throughout.
--
--   1. Lock down drip_subscribers, drip_log, user_settings (service_role only)
--   2. Functions: SECURITY DEFINER refresh_product_analytics, search_path hardening
--   3. Drift fix: set_scores.scarcity_score -> value_score, wider overall_grade CHECK
--   4. Drift fix: products.product_type CHECK (adds 'Booster Bundle Case')
--   5. alerts: alert_date + dedupe + unique index (one alert / product / type / day)
--   6. Lifecycle signal input: products.release_date backfill + insert trigger
--   7. drip_subscribers / drip_log constraints, indexes, updated_at triggers
--   8. product_analytics unique index, read-only grants on public tables
--
-- AFTER APPLYING: run `SELECT public.refresh_product_analytics();` once so the
-- materialized view picks up the backfilled products.release_date (section 6).
-- Look for WARNING messages in the output (duplicate drip e-mails, rows that
-- violate a new CHECK, ...). See supabase/README.md.

SET LOCAL lock_timeout = '30s';  -- fail fast (and roll back) instead of queueing behind a long scrape


-- ============================================================================
-- 1. SECURITY: drip_subscribers / drip_log / user_settings -> service_role only
-- ============================================================================
-- 012 created "Service role full access" policies WITHOUT `TO service_role`, so
-- they applied to every role, and Supabase's default privileges grant
-- anon/authenticated ALL on every new public table. user_settings (003) was
-- world-readable and has an e-mail column. These tables are only ever used with
-- the service-role key, so they get no access for the browser roles at all.
-- Fix = two independent layers: no table privileges for anon/authenticated AND
-- no RLS policy that applies to them.
DO $$
DECLARE
  t    text;
  pol  record;
  col  record;
  seq  text;
BEGIN
  FOREACH t IN ARRAY ARRAY['drip_subscribers', 'drip_log', 'user_settings'] LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'section 1: table public.% does not exist, skipping', t;
      CONTINUE;
    END IF;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);

    -- Drop EVERY existing policy (whatever it was called in the live DB), then
    -- recreate a single service_role-only one.
    FOR pol IN SELECT policyname FROM pg_policies WHERE schemaname = 'public' AND tablename = t LOOP
      EXECUTE format('DROP POLICY %I ON public.%I', pol.policyname, t);
    END LOOP;
    EXECUTE format(
      'CREATE POLICY "service_role only" ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)', t);

    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', t);
    EXECUTE format('GRANT ALL ON TABLE public.%I TO service_role', t);

    -- Sequences owned by the table's columns (none today: all PKs are UUIDs).
    FOR col IN SELECT attname FROM pg_attribute
               WHERE attrelid = ('public.' || t)::regclass AND attnum > 0 AND NOT attisdropped LOOP
      seq := pg_get_serial_sequence('public.' || t, col.attname);
      IF seq IS NOT NULL THEN
        EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC, anon, authenticated', seq);
        EXECUTE format('GRANT ALL ON SEQUENCE %s TO service_role', seq);
      END IF;
    END LOOP;
  END LOOP;
END $$;


-- ============================================================================
-- 2. FUNCTIONS (placed before the sections that use them)
-- ============================================================================

-- 2a. updated_at trigger function: same body as 001, now with a pinned search_path.
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- 2b. refresh_product_analytics(): was SECURITY INVOKER and EXECUTE-able by anon
-- through PostgREST RPC (anyone could force expensive refreshes). Now only
-- service_role may call it; it runs as the owner (postgres), who owns the view.
-- CONCURRENTLY is kept (all earlier definitions used it; it needs the unique
-- index ensured in section 8 and a populated view, hence the fallback). It is
-- allowed inside a transaction block, which is how PostgREST runs RPC calls
-- (verified in PGlite) and it keeps dashboard reads from blocking.
CREATE OR REPLACE FUNCTION public.refresh_product_analytics()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class
               WHERE oid = 'public.product_analytics'::regclass AND relispopulated) THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY public.product_analytics;
    ELSE
        REFRESH MATERIALIZED VIEW public.product_analytics;  -- CONCURRENTLY is illegal on an unpopulated view
    END IF;
END;
$$;

-- 2c. Trigger function: new products inherit the set's release date (section 6).
CREATE OR REPLACE FUNCTION public.products_fill_release_date()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.release_date IS NULL AND NEW.set_id IS NOT NULL THEN
        SELECT s.release_date INTO NEW.release_date FROM public.sets s WHERE s.id = NEW.set_id;
    END IF;
    RETURN NEW;
END;
$$;

-- 2d. Trigger function: keep drip_subscribers.email trimmed + lower-case so the
-- case-insensitive unique index (section 7) and ON CONFLICT (email) upserts agree.
CREATE OR REPLACE FUNCTION public.drip_subscribers_normalize_email()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    NEW.email := lower(btrim(NEW.email));
    RETURN NEW;
END;
$$;

-- Function privileges. Supabase default privileges grant EXECUTE on every new
-- public function to anon/authenticated, so PUBLIC alone is not enough.
REVOKE EXECUTE ON FUNCTION public.refresh_product_analytics()          FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.refresh_product_analytics()          TO service_role;
-- Trigger functions are not meant to be called directly (trigger firing does not
-- check EXECUTE; only CREATE TRIGGER does).
REVOKE EXECUTE ON FUNCTION public.update_updated_at_column()           FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.products_fill_release_date()         FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.drip_subscribers_normalize_email()   FROM PUBLIC, anon, authenticated;


-- ============================================================================
-- 3. SCHEMA DRIFT: set_scores (code is the source of truth)
-- ============================================================================
-- tools/seed_set_scores.py upserts `value_score`; 011 created `scarcity_score
-- NOT NULL`. The seed script can also emit +/- grades (compute_grade).
DO $$
DECLARE
  has_scarcity boolean;
  has_value    boolean;
  grade_att    smallint;
  value_att    smallint;
  con          record;
  bad          bigint;
BEGIN
  IF to_regclass('public.set_scores') IS NULL THEN
    RAISE NOTICE 'section 3: public.set_scores does not exist, skipping';
    RETURN;
  END IF;

  SELECT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'public.set_scores'::regclass
                 AND attname = 'scarcity_score' AND NOT attisdropped) INTO has_scarcity;
  SELECT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'public.set_scores'::regclass
                 AND attname = 'value_score' AND NOT attisdropped) INTO has_value;

  IF has_scarcity AND NOT has_value THEN
    -- Normal case: 011 as written. Rename; data, NOT NULL and CHECK follow the column.
    ALTER TABLE public.set_scores RENAME COLUMN scarcity_score TO value_score;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.set_scores'::regclass
               AND conname = 'set_scores_scarcity_score_check')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.set_scores'::regclass
                       AND conname = 'set_scores_value_score_check') THEN
      ALTER TABLE public.set_scores
        RENAME CONSTRAINT set_scores_scarcity_score_check TO set_scores_value_score_check;
    END IF;
  ELSIF NOT has_value THEN
    ALTER TABLE public.set_scores ADD COLUMN value_score INTEGER;
  ELSIF has_scarcity THEN
    -- Both exist (someone added value_score by hand): the code never writes
    -- scarcity_score, so its NOT NULL would reject every upsert.
    ALTER TABLE public.set_scores ALTER COLUMN scarcity_score DROP NOT NULL;
  END IF;

  -- value_score must carry a 1..10 CHECK (add one only if no CHECK covers that column yet).
  SELECT attnum INTO value_att FROM pg_attribute
   WHERE attrelid = 'public.set_scores'::regclass AND attname = 'value_score' AND NOT attisdropped;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid = 'public.set_scores'::regclass AND contype = 'c'
                   AND conkey = ARRAY[value_att]) THEN
    SELECT count(*) INTO bad FROM public.set_scores WHERE value_score NOT BETWEEN 1 AND 10;
    IF bad = 0 THEN
      ALTER TABLE public.set_scores
        ADD CONSTRAINT set_scores_value_score_check CHECK (value_score BETWEEN 1 AND 10);
    ELSE
      RAISE WARNING 'section 3: % set_scores row(s) have value_score outside 1..10; CHECK added NOT VALID (enforced for new writes only)', bad;
      ALTER TABLE public.set_scores
        ADD CONSTRAINT set_scores_value_score_check CHECK (value_score BETWEEN 1 AND 10) NOT VALID;
    END IF;
  END IF;

  -- overall_grade: replace whatever single-column CHECK exists with the full set
  -- compute_grade() can return: S, A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F.
  SELECT attnum INTO grade_att FROM pg_attribute
   WHERE attrelid = 'public.set_scores'::regclass AND attname = 'overall_grade' AND NOT attisdropped;
  FOR con IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'public.set_scores'::regclass AND contype = 'c'
               AND conkey = ARRAY[grade_att] LOOP
    EXECUTE format('ALTER TABLE public.set_scores DROP CONSTRAINT %I', con.conname);
  END LOOP;
  SELECT count(*) INTO bad FROM public.set_scores
   WHERE overall_grade NOT IN ('S','A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F');
  IF bad = 0 THEN
    ALTER TABLE public.set_scores ADD CONSTRAINT set_scores_overall_grade_check
      CHECK (overall_grade IN ('S','A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F'));
  ELSE
    RAISE WARNING 'section 3: % set_scores row(s) have an unexpected overall_grade; CHECK added NOT VALID', bad;
    ALTER TABLE public.set_scores ADD CONSTRAINT set_scores_overall_grade_check
      CHECK (overall_grade IN ('S','A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F')) NOT VALID;
  END IF;
END $$;


-- ============================================================================
-- 4. SCHEMA DRIFT: products.product_type CHECK
-- ============================================================================
-- tools/seed_products.py classify_product_type() can return exactly: 'Booster Box',
-- 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box', 'Booster Bundle Case',
-- 'Booster Bundle', 'Booster Pack', 'Collection Box', 'Other'. The 009 list lacked
-- 'Booster Bundle Case', so those upserts failed the CHECK.
DO $$
DECLARE
  bad_values text;
BEGIN
  ALTER TABLE public.products DROP CONSTRAINT IF EXISTS products_product_type_check;

  SELECT string_agg(DISTINCT product_type, ', ') INTO bad_values
    FROM public.products
   WHERE product_type NOT IN (
     'Booster Box', 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box',
     'Booster Pack', 'Booster Bundle', 'Booster Bundle Case', 'Collection Box', 'Other');

  IF bad_values IS NULL THEN
    ALTER TABLE public.products ADD CONSTRAINT products_product_type_check
      CHECK (product_type IN (
        'Booster Box', 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box',
        'Booster Pack', 'Booster Bundle', 'Booster Bundle Case', 'Collection Box', 'Other'));
  ELSE
    RAISE WARNING 'section 4: products has product_type values outside the allowed list (%); CHECK added NOT VALID (enforced for new writes only) -- fix or extend the list, then VALIDATE CONSTRAINT', bad_values;
    ALTER TABLE public.products ADD CONSTRAINT products_product_type_check
      CHECK (product_type IN (
        'Booster Box', 'Elite Trainer Box', 'Pokemon Center Elite Trainer Box',
        'Booster Pack', 'Booster Bundle', 'Booster Bundle Case', 'Collection Box', 'Other')) NOT VALID;
  END IF;
END $$;


-- ============================================================================
-- 5. ALERTS: one alert per (product, type, day)
-- ============================================================================
-- The daily pipeline inserted price_drop / price_spike alerts on every run while
-- the condition held. The Python side will upsert with
--   on_conflict='product_id,alert_type,alert_date' (ignore duplicates).
-- alert_date is a plain column (a generated column would need an IMMUTABLE
-- expression, and timezone() is only STABLE). NULL product_id rows never
-- conflict (NULLs are distinct in a unique index) and are left alone.
DO $$
DECLARE
  removed bigint;
BEGIN
  -- Block concurrent writers so no duplicate can slip in between DELETE and CREATE INDEX.
  LOCK TABLE public.alerts IN SHARE ROW EXCLUSIVE MODE;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'alert_date') THEN
    ALTER TABLE public.alerts
      ADD COLUMN alert_date DATE NOT NULL DEFAULT (timezone('utc', now()))::date;
    -- Backfill ONLY when we just added the column (re-runs must not rewrite it).
    UPDATE public.alerts SET alert_date = (timezone('utc', COALESCE(created_at, now())))::date;
  END IF;
  -- If the column pre-existed in some other shape, converge it.
  ALTER TABLE public.alerts ALTER COLUMN alert_date SET DEFAULT (timezone('utc', now()))::date;
  UPDATE public.alerts SET alert_date = (timezone('utc', COALESCE(created_at, now())))::date
   WHERE alert_date IS NULL;
  ALTER TABLE public.alerts ALTER COLUMN alert_date SET NOT NULL;

  -- Remove pre-existing duplicates: keep one row per (product, type, day),
  -- preferring a row that was already sent, then the earliest created_at.
  DELETE FROM public.alerts a
   USING (
     SELECT id,
            row_number() OVER (
              PARTITION BY product_id, alert_type, alert_date
              ORDER BY (is_sent IS TRUE) DESC, created_at ASC NULLS LAST, id ASC) AS rn
       FROM public.alerts
      WHERE product_id IS NOT NULL
   ) d
   WHERE a.id = d.id AND d.rn > 1;
  GET DIAGNOSTICS removed = ROW_COUNT;
  RAISE NOTICE 'section 5: removed % duplicate alert row(s)', removed;

  CREATE UNIQUE INDEX IF NOT EXISTS alerts_product_type_day_uidx
    ON public.alerts (product_id, alert_type, alert_date);
END $$;

CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON public.alerts (created_at DESC);


-- ============================================================================
-- 6. LIFECYCLE SIGNAL DATA: products.release_date
-- ============================================================================
-- Since 009 the product_analytics view exposes the PRODUCT's release_date, but
-- nothing populates it, so the lifecycle score input was NULL everywhere.
-- Backfill from the set now; new products inherit it via a BEFORE INSERT trigger
-- (this also covers upserts: Product.to_dict() sends release_date = null, and
-- BEFORE INSERT triggers run before ON CONFLICT resolution, so EXCLUDED holds
-- the filled value). The view definition is intentionally untouched.
UPDATE public.products p
   SET release_date = s.release_date
  FROM public.sets s
 WHERE p.set_id = s.id
   AND p.release_date IS NULL
   AND s.release_date IS NOT NULL;

DROP TRIGGER IF EXISTS products_fill_release_date ON public.products;
CREATE TRIGGER products_fill_release_date
    BEFORE INSERT ON public.products
    FOR EACH ROW
    WHEN (NEW.release_date IS NULL)
    EXECUTE FUNCTION public.products_fill_release_date();


-- ============================================================================
-- 7. DRIP TABLES: constraints, indexes, triggers
-- ============================================================================
DO $$
DECLARE
  dup_emails bigint;
  dup_tokens bigint;
BEGIN
  IF to_regclass('public.drip_subscribers') IS NULL THEN
    RAISE NOTICE 'section 7: public.drip_subscribers does not exist, skipping';
    RETURN;
  END IF;

  -- 8a. Case-insensitive unique e-mail.
  -- Normalise only rows whose normalised form collides with no other row
  -- (so this can never violate the existing UNIQUE(email) or lose a subscriber).
  UPDATE public.drip_subscribers d
     SET email = lower(btrim(d.email))
   WHERE d.email IS DISTINCT FROM lower(btrim(d.email))
     AND NOT EXISTS (SELECT 1 FROM public.drip_subscribers o
                      WHERE o.id <> d.id AND lower(btrim(o.email)) = lower(btrim(d.email)));

  SELECT count(*) INTO dup_emails FROM (
    SELECT 1 FROM public.drip_subscribers GROUP BY lower(btrim(email)) HAVING count(*) > 1) x;
  IF dup_emails > 0 THEN
    RAISE WARNING 'section 7: % set(s) of drip_subscribers differ only by e-mail case/whitespace; NOT creating drip_subscribers_email_lower_uidx and NOT deleting anyone. Inspect with: SELECT lower(btrim(email)), count(*) FROM drip_subscribers GROUP BY 1 HAVING count(*) > 1; merge/delete by hand, then re-run this migration.', dup_emails;
  ELSE
    CREATE UNIQUE INDEX IF NOT EXISTS drip_subscribers_email_lower_uidx
      ON public.drip_subscribers (lower(email));
  END IF;

  -- 8b. unsubscribe_token is the lookup key of /api/unsubscribe: never NULL, unique.
  UPDATE public.drip_subscribers SET unsubscribe_token = gen_random_uuid() WHERE unsubscribe_token IS NULL;
  ALTER TABLE public.drip_subscribers ALTER COLUMN unsubscribe_token SET DEFAULT gen_random_uuid();
  ALTER TABLE public.drip_subscribers ALTER COLUMN unsubscribe_token SET NOT NULL;

  SELECT count(*) INTO dup_tokens FROM (
    SELECT 1 FROM public.drip_subscribers GROUP BY unsubscribe_token HAVING count(*) > 1) x;
  IF dup_tokens > 0 THEN
    RAISE WARNING 'section 7: % duplicated unsubscribe_token value(s); NOT creating drip_subscribers_unsubscribe_token_uidx', dup_tokens;
  ELSE
    CREATE UNIQUE INDEX IF NOT EXISTS drip_subscribers_unsubscribe_token_uidx
      ON public.drip_subscribers (unsubscribe_token);
  END IF;
END $$;

-- Keep new/changed e-mails normalised (after the one-off normalisation above, so
-- that did not bump updated_at). Makes `upsert(..., onConflict: 'email')` match
-- 'Foo@X.com' against an existing 'foo@x.com' instead of hitting the lower() index.
DO $$
BEGIN
  IF to_regclass('public.drip_subscribers') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS drip_subscribers_normalize_email ON public.drip_subscribers;
    CREATE TRIGGER drip_subscribers_normalize_email
      BEFORE INSERT OR UPDATE OF email ON public.drip_subscribers
      FOR EACH ROW EXECUTE FUNCTION public.drip_subscribers_normalize_email();

    DROP TRIGGER IF EXISTS update_drip_subscribers_updated_at ON public.drip_subscribers;
    CREATE TRIGGER update_drip_subscribers_updated_at
      BEFORE UPDATE ON public.drip_subscribers
      FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
  END IF;

  IF to_regclass('public.drip_log') IS NOT NULL THEN
    CREATE INDEX IF NOT EXISTS idx_drip_log_subscriber_id ON public.drip_log (subscriber_id);
  END IF;

  IF to_regclass('public.set_scores') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS update_set_scores_updated_at ON public.set_scores;
    CREATE TRIGGER update_set_scores_updated_at
      BEFORE UPDATE ON public.set_scores
      FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
  END IF;
END $$;


-- ============================================================================
-- 8. product_analytics INDEX + GRANTS, PUBLIC-TABLE PRIVILEGES
-- ============================================================================
-- 8a. product_analytics: unique index (required by REFRESH ... CONCURRENTLY).
DO $$
BEGIN
  IF to_regclass('public.product_analytics') IS NOT NULL THEN
    CREATE UNIQUE INDEX IF NOT EXISTS idx_product_analytics_id
      ON public.product_analytics (product_id);
  END IF;
END $$;

-- 8b. Privileges on the public dashboard tables + view: read-only for the
-- browser roles. RLS already blocked their INSERT/UPDATE/DELETE (no write
-- policies), but TRUNCATE / REFERENCES / TRIGGER are not subject to RLS and
-- Supabase's default privileges grant them. Re-run this after EVERY recreate of
-- product_analytics: DROP + CREATE discards its grants.
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['sets', 'products', 'price_snapshots', 'sales_snapshots', 'signals',
                           'alerts', 'pull_rates', 'set_rarity_values', 'set_scores',
                           'product_analytics'] LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'section 8: relation public.% does not exist, skipping', t;
      CONTINUE;
    END IF;
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', t);
    EXECUTE format('GRANT SELECT ON TABLE public.%I TO anon, authenticated', t);
    EXECUTE format('GRANT ALL ON TABLE public.%I TO service_role', t);
  END LOOP;
END $$;

-- Make PostgREST pick up the new column / index / privileges immediately
-- (Supabase also reloads on DDL; this is just a belt-and-braces no-op elsewhere).
NOTIFY pgrst, 'reload schema';
