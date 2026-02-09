"""
Investigate TCGPlayer's internal APIs by intercepting network requests.

Launches Playwright, navigates to TCGPlayer pages, and captures all XHR/fetch
requests to discover usable API endpoints for pricing and product data.

Usage:
    python tools/investigate_tcgplayer.py
    python tools/investigate_tcgplayer.py --url "https://www.tcgplayer.com/product/512345/..."
    python tools/investigate_tcgplayer.py --search "pokemon scarlet violet booster box"
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from playwright.async_api import async_playwright

logger = logging.getLogger("investigate_tcgplayer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Known API patterns to watch for
API_PATTERNS = [
    "mp-search-api.tcgplayer.com",
    "mpapi.tcgplayer.com",
    "marketplace-api.tcgplayer.com",
    "graphql",
    "api.tcgplayer.com",
    "infinite-api.tcgplayer.com",
    "/v1/",
    "/v2/",
    "pricepoints",
    "marketprice",
    "product",
]


async def intercept_page(url: str, config: Config) -> list[dict]:
    """Navigate to a URL and capture all API requests/responses."""
    captured = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=config.random_user_agent(),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        async def on_response(response):
            req_url = response.url
            # Check if this matches any known API pattern
            is_api = any(pattern in req_url.lower() for pattern in API_PATTERNS)

            if not is_api:
                return

            entry = {
                "url": req_url,
                "method": response.request.method,
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "request_headers": dict(response.request.headers),
                "response_headers": dict(response.headers),
            }

            # Try to capture request body (for POST requests)
            try:
                post_data = response.request.post_data
                if post_data:
                    try:
                        entry["request_body"] = json.loads(post_data)
                    except json.JSONDecodeError:
                        entry["request_body"] = post_data
            except Exception:
                pass

            # Try to capture response body
            try:
                body = await response.body()
                text = body.decode("utf-8", errors="replace")
                if len(text) < 50000:  # Don't capture huge responses
                    try:
                        entry["response_body"] = json.loads(text)
                    except json.JSONDecodeError:
                        entry["response_body_preview"] = text[:2000]
            except Exception as e:
                entry["response_error"] = str(e)

            captured.append(entry)
            logger.info(f"  Captured: {response.request.method} {req_url[:120]} [{response.status}]")

        page.on("response", on_response)

        logger.info(f"Navigating to: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=config.playwright_timeout)
            # Wait a bit more for lazy-loaded data
            await page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"Page load issue (may still have captured data): {e}")

        # Scroll down to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        await browser.close()

    return captured


async def investigate_product_page(product_url: str, config: Config) -> list[dict]:
    """Investigate API calls made when loading a product page."""
    logger.info("=" * 60)
    logger.info("INVESTIGATING PRODUCT PAGE")
    logger.info("=" * 60)
    return await intercept_page(product_url, config)


async def investigate_search(query: str, config: Config) -> list[dict]:
    """Investigate API calls made when searching for products."""
    search_url = (
        f"{config.tcgplayer_base}/search/pokemon/product"
        f"?productLineName=pokemon&q={query}"
        f"&view=grid&productTypeName=Sealed%20Products"
    )
    logger.info("=" * 60)
    logger.info("INVESTIGATING SEARCH PAGE")
    logger.info("=" * 60)
    return await intercept_page(search_url, config)


async def investigate_category_page(config: Config) -> list[dict]:
    """Investigate API calls when browsing sealed Pokemon products."""
    cat_url = (
        f"{config.tcgplayer_base}/search/pokemon/product"
        f"?productLineName=pokemon"
        f"&productTypeName=Sealed%20Products"
        f"&view=grid"
    )
    logger.info("=" * 60)
    logger.info("INVESTIGATING CATEGORY BROWSE PAGE")
    logger.info("=" * 60)
    return await intercept_page(cat_url, config)


def summarize_endpoints(all_captured: list[dict]) -> dict:
    """Deduplicate and summarize discovered API endpoints."""
    endpoints = {}

    for entry in all_captured:
        # Create a key from the base URL (strip query params for grouping)
        url = entry["url"]
        base = url.split("?")[0]

        if base not in endpoints:
            endpoints[base] = {
                "url_pattern": base,
                "methods_seen": set(),
                "status_codes": set(),
                "content_type": entry.get("content_type", ""),
                "sample_request": None,
                "sample_response_keys": None,
                "hit_count": 0,
            }

        ep = endpoints[base]
        ep["methods_seen"].add(entry["method"])
        ep["status_codes"].add(entry["status"])
        ep["hit_count"] += 1

        # Store a sample request body
        if not ep["sample_request"] and entry.get("request_body"):
            ep["sample_request"] = entry["request_body"]

        # Store sample response keys
        if not ep["sample_response_keys"] and isinstance(entry.get("response_body"), dict):
            ep["sample_response_keys"] = list(entry["response_body"].keys())

    # Convert sets to lists for JSON serialization
    for ep in endpoints.values():
        ep["methods_seen"] = list(ep["methods_seen"])
        ep["status_codes"] = list(ep["status_codes"])

    return endpoints


async def main():
    parser = argparse.ArgumentParser(description="Investigate TCGPlayer internal APIs")
    parser.add_argument("--url", help="A specific TCGPlayer product URL to investigate")
    parser.add_argument("--search", help="A search query to investigate")
    parser.add_argument("--all", action="store_true", help="Run all investigation types")
    args = parser.parse_args()

    config = Config()
    all_captured = []

    # Default: investigate all if nothing specified
    if not args.url and not args.search:
        args.all = True

    if args.url:
        captured = await investigate_product_page(args.url, config)
        all_captured.extend(captured)

    if args.search:
        captured = await investigate_search(args.search, config)
        all_captured.extend(captured)

    if args.all:
        # Test with a known Pokemon sealed product
        test_url = f"{config.tcgplayer_base}/product/556996/pokemon-sv-scarlet-and-violet-151-booster-box"
        captured = await investigate_product_page(test_url, config)
        all_captured.extend(captured)

        await asyncio.sleep(2)

        captured = await investigate_search("pokemon booster box", config)
        all_captured.extend(captured)

        await asyncio.sleep(2)

        captured = await investigate_category_page(config)
        all_captured.extend(captured)

    # Summarize
    endpoints = summarize_endpoints(all_captured)

    # Save full results
    output_path = config.tmp_dir / "tcgplayer_api_map.json"
    output = {
        "investigation_summary": {
            "total_api_calls_captured": len(all_captured),
            "unique_endpoints": len(endpoints),
        },
        "endpoints": endpoints,
        "raw_captures": all_captured,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    logger.info("=" * 60)
    logger.info("INVESTIGATION COMPLETE")
    logger.info(f"  Total API calls captured: {len(all_captured)}")
    logger.info(f"  Unique endpoints found: {len(endpoints)}")
    logger.info(f"  Full results saved to: {output_path}")
    logger.info("=" * 60)

    # Print endpoint summary
    for base_url, info in sorted(endpoints.items()):
        logger.info(f"\n  ENDPOINT: {base_url}")
        logger.info(f"    Methods: {info['methods_seen']}")
        logger.info(f"    Status codes: {info['status_codes']}")
        logger.info(f"    Hit count: {info['hit_count']}")
        if info.get("sample_response_keys"):
            logger.info(f"    Response keys: {info['sample_response_keys']}")

    return output


if __name__ == "__main__":
    asyncio.run(main())
