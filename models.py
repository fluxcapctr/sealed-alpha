"""Domain models for the Pokemon sealed product investment tracker."""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date


@dataclass
class PokemonSet:
    """A Pokemon TCG set (e.g., 'Scarlet & Violet - 151')."""
    id: Optional[str] = None
    name: str = ""
    code: str = ""
    series: str = ""
    release_date: Optional[str] = None
    tcgplayer_group_id: Optional[int] = None
    set_url: str = ""
    image_url: str = ""
    is_in_print: bool = True
    is_in_rotation: bool = True
    total_products: int = 0
    language: str = "en"

    def to_dict(self) -> dict:
        d = asdict(self)
        # Remove None id for inserts
        if d["id"] is None:
            del d["id"]
        # Don't overwrite existing tcgplayer_group_id with None
        if d.get("tcgplayer_group_id") is None:
            d.pop("tcgplayer_group_id", None)
        return d


@dataclass
class Product:
    """A sealed product within a set."""
    id: Optional[str] = None
    set_id: Optional[str] = None
    name: str = ""
    product_type: str = ""
    tcgplayer_product_id: Optional[int] = None
    tcgplayer_url: str = ""
    image_url: str = ""
    release_date: Optional[str] = None
    msrp: Optional[float] = None
    is_active: bool = True
    language: str = "en"

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["id"] is None:
            del d["id"]
        return d


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
