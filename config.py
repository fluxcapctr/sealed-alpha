"""Centralized configuration. Loads from .env with sensible defaults."""

import os
import random
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

PROJECT_ROOT = Path(__file__).parent


def _env(name: str, default: str = "") -> str:
    """Read an env var, treating unset AND empty/blank as 'use the default'.

    GitHub Actions passes an unset secret as an empty string, which os.getenv()
    returns as-is instead of applying its default.
    """
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


@dataclass
class Config:
    # Supabase
    supabase_url: str = field(
        default_factory=lambda: _env("SUPABASE_URL")
    )
    supabase_anon_key: str = field(
        default_factory=lambda: _env("SUPABASE_ANON_KEY")
    )
    supabase_service_role_key: str = field(
        default_factory=lambda: _env("SUPABASE_SERVICE_ROLE_KEY")
    )

    # Timeouts
    httpx_timeout: int = 30
    playwright_timeout: int = 30000

    # Rate limiting
    request_delay: float = field(
        default_factory=lambda: float(_env("REQUEST_DELAY", "2.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(_env("MAX_RETRIES", "3"))
    )
    retry_backoff_base: float = 2.0

    # User-Agent rotation
    user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    ])

    # Proxy
    proxy_url: str | None = field(
        default_factory=lambda: _env("PROXY_URL") or None
    )

    # Paths
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    tmp_dir: Path = field(default_factory=lambda: PROJECT_ROOT / ".tmp")

    # TCGPlayer
    tcgplayer_base: str = "https://www.tcgplayer.com"
    tcgplayer_search_api: str = "https://mp-search-api.tcgplayer.com/v1/search/request"
    tcgplayer_product_api: str = "https://mpapi.tcgplayer.com/v2/product"
    tcgplayer_category_id: int = 3  # Pokemon = category 3 on TCGPlayer

    # Product types to track (English)
    product_types: list[str] = field(default_factory=lambda: [
        "Booster Box",
        "Elite Trainer Box",
        "Pokemon Center Elite Trainer Box",
        "Booster Pack",
        "Collection Box",
    ])

    # Product types to track (Japanese) — broader since JP has fewer standardized types
    product_types_jp: list[str] = field(default_factory=lambda: [
        "Booster Box",
        "Booster Pack",
        "Collection Box",
        "Elite Trainer Box",
        "Other",
    ])

    # Set year range (XY era = 2014, SM = 2017, SWSH = 2020, SV = 2023)
    min_set_year: int = 2014

    # Scrape scheduling thresholds (days between scrapes)
    schedule_new_days: int = 1       # Sets < 1 year old → daily
    schedule_mid_days: int = 3       # Sets 1-3 years old → every 3 days
    schedule_old_days: int = 7       # Sets 3+ years old → weekly
    new_set_threshold_days: int = 365
    old_set_threshold_days: int = 1095

    # Pipeline health: fraction of in-scope active products that must get a price
    # snapshot on a daily run, and of set queries that may fail, before the run
    # is reported as failed (non-zero exit).
    min_price_coverage: float = field(
        default_factory=lambda: float(_env("MIN_PRICE_COVERAGE", "0.85"))
    )
    max_failed_query_fraction: float = 0.25

    # Logging
    log_level: str = field(
        default_factory=lambda: _env("LOG_LEVEL", "INFO")
    )

    # Email (Phase 5)
    resend_api_key: str = field(
        default_factory=lambda: _env("RESEND_API_KEY")
    )
    alert_email: str = field(
        default_factory=lambda: _env("ALERT_EMAIL")
    )

    # Drip Campaign
    wholesale_url: str = field(
        default_factory=lambda: _env("WHOLESALE_URL", "https://kitakamicards.com")
    )
    drip_sender_email: str = field(
        default_factory=lambda: _env("DRIP_SENDER_EMAIL", "onboarding@resend.dev")
    )

    def __post_init__(self):
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def require_supabase(self) -> None:
        """Fail fast with a readable message instead of an obscure client error."""
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Set them in .env (see .env.example) or the CI secrets."
            )

    def random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def random_delay(self) -> float:
        """Return a randomized delay between 0.5x and 1.5x the base delay."""
        return self.request_delay * random.uniform(0.5, 1.5)
