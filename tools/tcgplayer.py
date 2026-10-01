"""
Shared TCGPlayer client used by the price, quantity and product-seeding tools.

TCGPlayer's marketplace search API is undocumented. What the tools rely on was
checked against the live API (2026-09-30):

- Page size is capped at 50. A larger `size` is rejected with HTTP 400.
- `totalResults` is the full match count for the query; page with `from`.
- A result's `marketPrice` equals the product's `/pricepoints` marketPrice.
- A result's `setId` is the TCGPlayer group id and `setName` the TCGPlayer set
  name (e.g. "SV: Scarlet & Violet 151"). Our `sets.name` comes from
  pokemontcg.io ("151"), so a `q=<our name>` query is a fuzzy match: it also
  returns products from other sets and, for generic names such as
  "Sword & Shield", more than 50 matches.
- `lowestPrice` is the cheapest single listing and can be a wildly low outlier
  (151 ETB: lowest $59.88 vs market $491.68); `medianPrice` is more robust.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from config import Config

logger = logging.getLogger("tcgplayer")

SEARCH_API = "https://mp-search-api.tcgplayer.com/v1/search/request"
LISTINGS_API = "https://mp-search-api.tcgplayer.com/v1/product"
PRICEPOINTS_API = "https://mpapi.tcgplayer.com/v2/product"

PAGE_SIZE = 50  # the API returns HTTP 400 for anything larger
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_SECONDS = 60.0

Sleep = Callable[[float], Awaitable[None]]


class TcgPlayerError(Exception):
    """A request failed permanently (non-retryable status) or ran out of retries."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class SearchResult:
    items: list[dict] = field(default_factory=list)
    total: int = 0
    truncated: bool = False  # fewer items returned than the API says exist


def product_line_for(language: str | None) -> str:
    return "pokemon-japan" if language == "ja" else "pokemon"


def clean_price(value: Any) -> float | None:
    """A usable price: finite and > 0. TCGPlayer uses null (and sometimes 0) for 'no data'."""
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0:
        return None
    return round(price, 2)


def clean_count(value: Any) -> int | None:
    """A non-negative count. 0 is a real value (no listings); None means unknown."""
    try:
        count = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return count if count >= 0 else None


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return min(max(float(raw), 0.0), MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        return None


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    config: Config,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    sleep: Sleep = asyncio.sleep,
) -> Any:
    """
    Send a request and return the parsed JSON body.

    Retries transport errors, timeouts, 429 and 5xx (honouring Retry-After) with
    exponential backoff. Any other non-200 status raises TcgPlayerError at once
    with `.status` set, so callers can tell "not found" from "blocked".
    """
    last_problem = "no attempts made"
    for attempt in range(config.max_retries):
        wait = config.retry_backoff_base ** (attempt + 1)
        try:
            resp = await client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers={"User-Agent": config.random_user_agent()},
            )
        except httpx.TransportError as e:  # includes timeouts and connection errors
            last_problem = f"{type(e).__name__}: {e}"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    last_problem = "HTTP 200 with a non-JSON body"
            elif resp.status_code in RETRYABLE_STATUS:
                last_problem = f"HTTP {resp.status_code}"
                wait = _retry_after(resp) or wait
            else:
                raise TcgPlayerError(
                    f"HTTP {resp.status_code} from {url}", status=resp.status_code
                )

        if attempt < config.max_retries - 1:
            logger.warning(f"{last_problem} from {url}; retrying in {wait:.1f}s")
            await sleep(wait)

    raise TcgPlayerError(f"gave up on {url} after {config.max_retries} attempts: {last_problem}")


def build_search_payload(product_line: str, offset: int = 0) -> dict:
    return {
        "algorithm": "sales_synonym_v2",
        "from": offset,
        "size": PAGE_SIZE,
        "filters": {
            "term": {
                "productLineName": [product_line],
                "productTypeName": ["Sealed Products"],
            },
            "range": {},
            "match": {},
        },
        "listingSearch": {
            "filters": {
                "term": {},
                "range": {},
                "exclude": {"channelExclusion": 0},
            }
        },
        "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
        "settings": {"useFuzzySearch": True, "didYouMean": {}},
        "sort": {},
    }


async def search_sealed(
    client: httpx.AsyncClient,
    query: str,
    product_line: str,
    config: Config,
    *,
    max_pages: int = 4,
    sleep: Sleep = asyncio.sleep,
) -> SearchResult:
    """
    Fuzzy-search sealed products and page through the results (up to `max_pages`).

    A failure on the first page raises TcgPlayerError. A failure on a later page
    keeps what was already fetched and marks the result truncated, so one flaky
    page does not discard 50 good rows.
    """
    result = SearchResult()
    seen: set[int] = set()
    offset = 0

    for page in range(max_pages):
        try:
            data = await request_json(
                client,
                "POST",
                SEARCH_API,
                config,
                params={"q": query, "isList": "false"},
                json_body=build_search_payload(product_line, offset),
                sleep=sleep,
            )
        except TcgPlayerError as e:
            if page == 0:
                raise
            logger.warning(f"Search '{query}' page {page + 1} failed, keeping partial results: {e}")
            result.truncated = True
            return result

        blocks = data.get("results") or [{}]
        if page == 0:
            result.total = clean_count(blocks[0].get("totalResults")) or 0

        page_items = [item for block in blocks for item in (block.get("results") or [])]
        for item in page_items:
            raw_id = item.get("productId")
            product_id = clean_count(raw_id)
            if product_id is None or product_id in seen:
                continue
            seen.add(product_id)
            result.items.append(item)

        offset += PAGE_SIZE
        if not page_items or offset >= result.total:
            break
        await sleep(config.random_delay())

    result.truncated = len(result.items) < result.total
    return result


async def fetch_pricepoints(
    client: httpx.AsyncClient, tcgplayer_id: int, config: Config, *, sleep: Sleep = asyncio.sleep
) -> Any:
    """Per-product price points: [{printingType, marketPrice, listedMedianPrice}, ...]."""
    return await request_json(
        client, "GET", f"{PRICEPOINTS_API}/{tcgplayer_id}/pricepoints", config, sleep=sleep
    )


async def fetch_listing_quantity(
    client: httpx.AsyncClient, tcgplayer_id: int, config: Config, *, sleep: Sleep = asyncio.sleep
) -> int:
    """
    Total units for sale across all live US listings.

    The listings endpoint buckets listings by their `quantity`; the sum of
    value * count over the buckets is the unit total (checked: 63 listings,
    146 units for 151 ETB). Returns 0 when the product has no live listings and
    raises TcgPlayerError when the response cannot be interpreted, so callers
    never mistake "failed to fetch" for "sold out".
    """
    payload = {
        "filters": {
            "term": {"sellerStatus": "Live", "channelId": [0]},
            "range": {"quantity": {"gte": 1}},
            "exclude": {"channelExclusion": 0},
        },
        "from": 0,
        "size": 0,
        "sort": {"field": "price+shipping", "order": "asc"},
        "context": {"shippingCountry": "US", "cart": {}},
        "aggregations": ["quantity"],
    }
    data = await request_json(
        client, "POST", f"{LISTINGS_API}/{tcgplayer_id}/listings", config,
        json_body=payload, sleep=sleep,
    )

    blocks = data.get("results") or []
    if not blocks:
        raise TcgPlayerError(f"listings response for {tcgplayer_id} has no results block")
    block = blocks[0]
    total_listings = clean_count(block.get("totalResults")) or 0
    buckets = (block.get("aggregations") or {}).get("quantity") or []

    if not buckets:
        if total_listings == 0:
            return 0
        raise TcgPlayerError(
            f"listings response for {tcgplayer_id} reports {total_listings} listings "
            "but no quantity aggregation"
        )

    try:
        return sum(int(b["value"]) * int(b["count"]) for b in buckets)
    except (KeyError, TypeError, ValueError) as e:
        raise TcgPlayerError(f"unreadable quantity buckets for {tcgplayer_id}: {e}") from e
