"""Supabase database layer. CRUD helpers for all tables."""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable

from supabase import create_client, Client

from config import Config
from models import PokemonSet, Product, PriceSnapshot, SalesSnapshot, Signal, Alert

logger = logging.getLogger(__name__)

# PostgREST returns at most 1000 rows per request by default and silently
# truncates anything longer, so every unbounded read goes through fetch_all().
PAGE_SIZE = 1000
UNIQUE_VIOLATION = "23505"


def _chunks(rows: list, size: int) -> Iterable[list]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


class Database:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.config.require_supabase()
        self.client: Client = create_client(
            self.config.supabase_url,
            self.config.supabase_service_role_key,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def fetch_all(build: Callable[[int, int], object], page_size: int = PAGE_SIZE) -> list[dict]:
        """
        Read every row of a query, one page at a time.

        `build(start, end)` must return a fresh query with `.range(start, end)`
        applied and a deterministic `.order(...)` that ends in a unique column
        (id / product_id). Without a total order, rows can be skipped or
        repeated across page boundaries.
        """
        rows: list[dict] = []
        start = 0
        while True:
            page = build(start, start + page_size - 1).execute().data or []
            rows.extend(page)
            if len(page) < page_size:
                return rows
            start += page_size

    def bulk_upsert(
        self,
        table: str,
        rows: list[dict],
        on_conflict: str,
        chunk_size: int = 500,
    ) -> tuple[int, list[dict]]:
        """
        Upsert many rows in few requests. Returns (rows_written, rows_failed).

        Rows are grouped by their set of keys before sending: PostgREST writes
        NULL into any column missing from some rows of a mixed batch, which
        would wipe values (e.g. a quantity written by a later step) that those
        rows never meant to touch. If a chunk is rejected it is retried row by
        row so one bad row does not lose the other 499.
        """
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
            groups[tuple(sorted(row))].append(row)

        written = 0
        failed: list[dict] = []
        for group in groups.values():
            for chunk in _chunks(group, chunk_size):
                try:
                    self.client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
                    written += len(chunk)
                except Exception as e:
                    logger.warning(
                        f"Bulk upsert into {table} failed for {len(chunk)} rows ({e}); retrying row by row"
                    )
                    for row in chunk:
                        try:
                            self.client.table(table).upsert(row, on_conflict=on_conflict).execute()
                            written += 1
                        except Exception as row_error:
                            logger.error(f"  {table} row rejected: {row_error} | {row}")
                            failed.append(row)
        return written, failed

    # ------------------------------------------------------------------
    # Sets
    # ------------------------------------------------------------------

    def upsert_set(self, s: PokemonSet) -> dict:
        """Insert or update a set. Uses (code, language) for conflict resolution."""
        data = s.to_dict()
        result = (
            self.client.table("sets")
            .upsert(data, on_conflict="code,language")
            .execute()
        )
        return result.data[0] if result.data else {}

    def get_sets(self, in_print: bool | None = None, language: str | None = None) -> list[dict]:
        def build(start: int, end: int):
            query = (
                self.client.table("sets")
                .select("*")
                .order("release_date", desc=True)
                .order("id")
                .range(start, end)
            )
            if in_print is not None:
                query = query.eq("is_in_print", in_print)
            if language is not None:
                query = query.eq("language", language)
            return query

        return self.fetch_all(build)

    def get_set_by_group_id(self, group_id: int) -> dict | None:
        result = (
            self.client.table("sets")
            .select("*")
            .eq("tcgplayer_group_id", group_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_set_by_id(self, set_id: str) -> dict | None:
        result = (
            self.client.table("sets")
            .select("*")
            .eq("id", set_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def upsert_product(self, p: Product) -> dict:
        """Insert or update a product. Uses tcgplayer_product_id for conflict resolution."""
        data = p.to_dict()
        result = (
            self.client.table("products")
            .upsert(data, on_conflict="tcgplayer_product_id")
            .execute()
        )
        return result.data[0] if result.data else {}

    def get_products(
        self,
        set_id: str | None = None,
        product_type: str | None = None,
        is_active: bool = True,
        language: str | None = None,
    ) -> list[dict]:
        def build(start: int, end: int):
            query = (
                self.client.table("products")
                .select("*, sets(name, code, release_date, is_in_print, is_in_rotation)")
                .eq("is_active", is_active)
                .order("name")
                .order("id")  # names repeat; without a unique tiebreak pages skip/duplicate rows
                .range(start, end)
            )
            if set_id:
                query = query.eq("set_id", set_id)
            if product_type:
                query = query.eq("product_type", product_type)
            if language is not None:
                query = query.eq("language", language)
            return query

        return self.fetch_all(build)

    def get_existing_products_by_tcgplayer_ids(self, tcgplayer_ids: list[int]) -> dict[int, dict]:
        """Map tcgplayer_product_id -> {id, set_id, ...} for the ids that already exist."""
        found: dict[int, dict] = {}
        for chunk in _chunks(sorted(set(tcgplayer_ids)), 100):
            rows = (
                self.client.table("products")
                .select("id, set_id, name, tcgplayer_product_id")
                .in_("tcgplayer_product_id", chunk)
                .execute()
                .data
                or []
            )
            for row in rows:
                found[int(row["tcgplayer_product_id"])] = row
        return found

    def get_product_by_tcgplayer_id(self, tcgplayer_id: int) -> dict | None:
        result = (
            self.client.table("products")
            .select("*")
            .eq("tcgplayer_product_id", tcgplayer_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_product_by_id(self, product_id: str) -> dict | None:
        result = (
            self.client.table("products")
            .select("*, sets(name, code, release_date, is_in_print, is_in_rotation)")
            .eq("id", product_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_products_needing_scrape(self) -> list[dict]:
        """Get products that are due for a price scrape based on their set age."""
        config = self.config
        today = date.today()

        products = self.get_products(is_active=True)
        last_snapshot = self.get_last_snapshot_dates()
        due = []

        for p in products:
            set_data = p.get("sets") or {}
            release_str = set_data.get("release_date") or p.get("release_date")

            if release_str:
                release = date.fromisoformat(release_str)
                age_days = (today - release).days
            else:
                age_days = 9999  # Unknown age — treat as old

            if age_days < config.new_set_threshold_days:
                interval = config.schedule_new_days
            elif age_days < config.old_set_threshold_days:
                interval = config.schedule_mid_days
            else:
                interval = config.schedule_old_days

            # Check last scrape date
            last_date_str = last_snapshot.get(p["id"])
            if last_date_str:
                days_since = (today - date.fromisoformat(last_date_str)).days
                if days_since < interval:
                    continue

            due.append(p)

        return due

    def get_last_snapshot_dates(self) -> dict[str, str]:
        """
        product_id -> date of its most recent price snapshot, in ~2 requests.

        Reads product_analytics.last_tracked rather than price_snapshots (hundreds of
        thousands of rows) or one query per product. The view is refreshed at the end
        of every daily run, so it is at most a day behind, which is fine for deciding
        whether a product is due for a re-scrape.
        """
        rows = self.fetch_all(
            lambda start, end: (
                self.client.table("product_analytics")
                .select("product_id, last_tracked")
                .order("product_id")
                .range(start, end)
            )
        )
        return {r["product_id"]: r["last_tracked"] for r in rows if r.get("last_tracked")}

    # ------------------------------------------------------------------
    # Price Snapshots
    # ------------------------------------------------------------------

    def insert_price_snapshot(self, snap: PriceSnapshot) -> dict:
        """Insert a price snapshot. Uses (product_id, snapshot_date) uniqueness."""
        data = snap.to_dict()
        result = (
            self.client.table("price_snapshots")
            .upsert(data, on_conflict="product_id,snapshot_date")
            .execute()
        )
        return result.data[0] if result.data else {}

    def insert_price_snapshots(self, snaps: list[PriceSnapshot]) -> tuple[int, list[dict]]:
        """Bulk version of insert_price_snapshot. Returns (written, failed_rows)."""
        return self.bulk_upsert(
            "price_snapshots",
            [snap.to_dict() for snap in snaps],
            on_conflict="product_id,snapshot_date",
        )

    def set_snapshot_quantity(self, product_id: str, snapshot_date: str, quantity: int) -> int:
        """Set available_quantity on an existing snapshot. Returns rows updated (0 = no snapshot that day)."""
        result = (
            self.client.table("price_snapshots")
            .update({"available_quantity": quantity})
            .eq("product_id", product_id)
            .eq("snapshot_date", snapshot_date)
            .execute()
        )
        return len(result.data or [])

    def get_price_history(
        self, product_id: str, days: int = 365
    ) -> list[dict]:
        since = str(date.today() - timedelta(days=days))
        return (
            self.client.table("price_snapshots")
            .select("*")
            .eq("product_id", product_id)
            .gte("snapshot_date", since)
            .order("snapshot_date")
            .execute()
            .data
        )

    def get_latest_price(self, product_id: str) -> dict | None:
        result = (
            self.client.table("price_snapshots")
            .select("*")
            .eq("product_id", product_id)
            .order("snapshot_date", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # ------------------------------------------------------------------
    # Sales Snapshots
    # ------------------------------------------------------------------

    def insert_sales_snapshot(self, snap: SalesSnapshot) -> dict:
        data = snap.to_dict()
        result = (
            self.client.table("sales_snapshots")
            .upsert(data, on_conflict="product_id,snapshot_date")
            .execute()
        )
        return result.data[0] if result.data else {}

    def get_sales_history(
        self, product_id: str, days: int = 90
    ) -> list[dict]:
        since = str(date.today() - timedelta(days=days))
        return (
            self.client.table("sales_snapshots")
            .select("*")
            .eq("product_id", product_id)
            .gte("snapshot_date", since)
            .order("snapshot_date")
            .execute()
            .data
        )

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def create_alert(self, alert: Alert) -> dict:
        data = alert.to_dict()
        result = self.client.table("alerts").insert(data).execute()
        return result.data[0] if result.data else {}

    def create_alerts(self, alerts: list[Alert]) -> int:
        """
        Insert alerts, at most one per (product, alert_type) per UTC day.

        The pipeline re-evaluates every product on every run, so a condition that
        holds for a week (e.g. "dropped 12% in 7 days") would otherwise insert a
        new alert daily, and a rerun the same day would duplicate them. Existing
        alerts from today are looked up first; migration 013's unique index on
        (product_id, alert_type, alert_date) backs this up against races.
        Returns the number of alerts inserted.
        """
        if not alerts:
            return 0

        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        existing_rows = self.fetch_all(
            lambda start, end: (
                self.client.table("alerts")
                .select("id, product_id, alert_type")
                .gte("created_at", day_start.isoformat())
                .order("id")
                .range(start, end)
            )
        )
        taken = {(r["product_id"], r["alert_type"]) for r in existing_rows}

        fresh: list[dict] = []
        for alert in alerts:
            key = (alert.product_id, alert.alert_type)
            if key in taken:
                continue
            taken.add(key)
            fresh.append(alert.to_dict())

        inserted = 0
        for chunk in _chunks(fresh, 500):
            try:
                self.client.table("alerts").insert(chunk).execute()
                inserted += len(chunk)
            except Exception as e:
                logger.warning(f"Bulk alert insert failed ({e}); retrying row by row")
                for row in chunk:
                    try:
                        self.client.table("alerts").insert(row).execute()
                        inserted += 1
                    except Exception as row_error:
                        if UNIQUE_VIOLATION in str(row_error):
                            continue  # another run created it first
                        logger.error(f"  alert rejected: {row_error} | {row}")
        return inserted

    def get_pending_alerts(self) -> list[dict]:
        return self.fetch_all(
            lambda start, end: (
                self.client.table("alerts")
                .select("*, products(name, tcgplayer_url)")
                .eq("is_sent", False)
                .order("created_at", desc=True)
                .order("id")
                .range(start, end)
            )
        )

    def mark_alert_sent(self, alert_id: str) -> None:
        self.client.table("alerts").update(
            {"is_sent": True, "sent_at": "now()"}
        ).eq("id", alert_id).execute()

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def upsert_signal(self, sig: Signal) -> dict:
        data = sig.to_dict()
        result = (
            self.client.table("signals")
            .upsert(data, on_conflict="product_id,signal_date")
            .execute()
        )
        return result.data[0] if result.data else {}

    def upsert_signals(self, signals: list[Signal]) -> tuple[int, list[dict]]:
        """Bulk upsert. Returns (written, failed_rows)."""
        return self.bulk_upsert(
            "signals",
            [sig.to_dict() for sig in signals],
            on_conflict="product_id,signal_date",
        )

    def get_previous_signals(self, before: str, lookback_days: int = 7) -> dict[str, dict]:
        """
        product_id -> most recent signal row dated before `before` (within the lookback window).

        Used to detect Hold -> Buy/Sell crossings. A product with no signal in the
        window simply produces no crossing alert.
        """
        since = str(date.fromisoformat(before) - timedelta(days=lookback_days))
        rows = self.fetch_all(
            lambda start, end: (
                self.client.table("signals")
                .select("product_id, signal_date, recommendation, composite_score")
                .gte("signal_date", since)
                .lt("signal_date", before)
                .order("signal_date", desc=True)
                .order("product_id")
                .range(start, end)
            )
        )
        previous: dict[str, dict] = {}
        for row in rows:  # newest first, so the first sighting wins
            previous.setdefault(row["product_id"], row)
        return previous

    def get_latest_signals(
        self, min_score: float | None = None, limit: int = 50
    ) -> list[dict]:
        query = (
            self.client.table("signals")
            .select("*, products(name, product_type, tcgplayer_url, sets(name))")
            .order("signal_date", desc=True)
            .order("composite_score", desc=True)
            .limit(limit)
        )
        if min_score is not None:
            query = query.gte("composite_score", min_score)
        return query.execute().data

    # ------------------------------------------------------------------
    # Analytics View
    # ------------------------------------------------------------------

    def get_product_analytics(self, product_id: str | None = None) -> list[dict]:
        def build(start: int, end: int):
            query = (
                self.client.table("product_analytics")
                .select("*")
                .order("product_id")
                .range(start, end)
            )
            if product_id:
                query = query.eq("product_id", product_id)
            return query

        return self.fetch_all(build)

    def refresh_analytics(self) -> None:
        """Refresh the product_analytics materialized view. Raises if the refresh fails."""
        self.client.rpc("refresh_product_analytics").execute()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        def count(query) -> int:
            # limit(1): we only want the exact count header, not the rows themselves
            return query.limit(1).execute().count or 0

        sets_count = count(self.client.table("sets").select("id", count="exact"))
        products_count = count(
            self.client.table("products").select("id", count="exact").eq("is_active", True)
        )
        snapshots_count = count(self.client.table("price_snapshots").select("id", count="exact"))
        return {
            "total_sets": sets_count,
            "total_products": products_count,
            "total_snapshots": snapshots_count,
        }
