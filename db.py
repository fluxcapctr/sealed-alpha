"""Supabase database layer. CRUD helpers for all tables."""

import logging
from datetime import date, timedelta

from supabase import create_client, Client

from config import Config
from models import PokemonSet, Product, PriceSnapshot, SalesSnapshot, Signal, Alert

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.client: Client = create_client(
            self.config.supabase_url,
            self.config.supabase_service_role_key,
        )

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
        query = self.client.table("sets").select("*").order("release_date", desc=True)
        if in_print is not None:
            query = query.eq("is_in_print", in_print)
        if language is not None:
            query = query.eq("language", language)
        return query.execute().data

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
        # Paginate to avoid Supabase default 1000-row limit
        all_data: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            query = (
                self.client.table("products")
                .select("*, sets(name, code, release_date, is_in_print, is_in_rotation)")
                .eq("is_active", is_active)
                .order("name")
                .range(offset, offset + page_size - 1)
            )
            if set_id:
                query = query.eq("set_id", set_id)
            if product_type:
                query = query.eq("product_type", product_type)
            if language is not None:
                query = query.eq("language", language)
            data = query.execute().data
            all_data.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
        return all_data

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
        due = []

        for p in products:
            set_data = p.get("sets", {})
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
            latest = self.get_latest_price(p["id"])
            if latest:
                last_date = date.fromisoformat(latest["snapshot_date"])
                days_since = (today - last_date).days
                if days_since < interval:
                    continue

            due.append(p)

        return due

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

    def get_pending_alerts(self) -> list[dict]:
        return (
            self.client.table("alerts")
            .select("*, products(name, tcgplayer_url)")
            .eq("is_sent", False)
            .order("created_at", desc=True)
            .execute()
            .data
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
        query = self.client.table("product_analytics").select("*")
        if product_id:
            query = query.eq("product_id", product_id)
        return query.execute().data

    def refresh_analytics(self) -> None:
        """Refresh the product_analytics materialized view."""
        self.client.rpc("refresh_product_analytics").execute()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        sets_count = len(self.client.table("sets").select("id", count="exact").execute().data)
        products_count = len(
            self.client.table("products").select("id", count="exact").eq("is_active", True).execute().data
        )
        snapshots_count = len(
            self.client.table("price_snapshots").select("id", count="exact").execute().data
        )
        return {
            "total_sets": sets_count,
            "total_products": products_count,
            "total_snapshots": snapshots_count,
        }
