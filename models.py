"""Domain models for the Pokemon sealed product investment tracker."""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date


def _drop_unset(d: dict, required: tuple[str, ...] = ()) -> dict:
    """
    Keep only fields the caller actually set.

    These dicts are sent to PostgREST as upserts, and an upsert overwrites every
    column that is present in the payload. Dropping None and "" means re-seeding
    a row never blanks values written by other tools (logos, release dates,
    MSRP, manual is_active / is_in_print changes). The DB column defaults still
    apply when a row is first inserted.
    """
    return {k: v for k, v in d.items() if k in required or (v is not None and v != "")}


@dataclass
class PokemonSet:
    """A Pokemon TCG set (e.g., 'Scarlet & Violet - 151').

    Leave a field unset (None / "") to keep whatever is already stored.
    """
    id: Optional[str] = None
    name: str = ""
    code: str = ""
    series: str = ""
    release_date: Optional[str] = None
    tcgplayer_group_id: Optional[int] = None
    set_url: str = ""
    image_url: str = ""
    is_in_print: Optional[bool] = None
    is_in_rotation: Optional[bool] = None
    total_products: Optional[int] = None
    language: str = "en"

    def to_dict(self) -> dict:
        return _drop_unset(asdict(self), required=("name", "code", "language"))


@dataclass
class Product:
    """A sealed product within a set.

    Leave a field unset (None / "") to keep whatever is already stored.
    """
    id: Optional[str] = None
    set_id: Optional[str] = None
    name: str = ""
    product_type: str = ""
    tcgplayer_product_id: Optional[int] = None
    tcgplayer_url: str = ""
    image_url: str = ""
    release_date: Optional[str] = None
    msrp: Optional[float] = None
    is_active: Optional[bool] = None
    language: str = "en"

    def to_dict(self) -> dict:
        return _drop_unset(asdict(self), required=("name", "product_type", "language"))


@dataclass
class PriceSnapshot:
    """A point-in-time price observation."""
    id: Optional[str] = None
    product_id: Optional[str] = None
    snapshot_date: Optional[str] = None
    market_price: Optional[float] = None
    low_price: Optional[float] = None
    mid_price: Optional[float] = None
    high_price: Optional[float] = None
    listed_median_price: Optional[float] = None
    direct_low_price: Optional[float] = None
    total_listings: Optional[int] = None
    available_quantity: Optional[int] = None
    foil_price: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["id"] is None:
            del d["id"]
        # Remove None values so Supabase uses defaults
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class SalesSnapshot:
    """Daily sales volume observation."""
    id: Optional[str] = None
    product_id: Optional[str] = None
    snapshot_date: Optional[str] = None
    total_sales: Optional[int] = None
    avg_sale_price: Optional[float] = None
    min_sale_price: Optional[float] = None
    max_sale_price: Optional[float] = None
    sale_count_24h: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["id"] is None:
            del d["id"]
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Signal:
    """Computed buy/sell signal for a product."""
    product_id: str = ""
    signal_date: str = field(default_factory=lambda: str(date.today()))
    composite_score: float = 0.0
    price_vs_ma_score: float = 0.0
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    listings_score: float = 0.0
    sales_velocity_score: float = 0.0
    lifecycle_score: float = 0.0
    recommendation: str = "HOLD"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Alert:
    """A triggered alert for a product."""
    id: Optional[str] = None
    product_id: Optional[str] = None
    alert_type: str = ""
    message: str = ""
    signal_score: Optional[float] = None
    is_sent: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["id"] is None:
            del d["id"]
        return {k: v for k, v in d.items() if v is not None}
