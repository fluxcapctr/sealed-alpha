from types import SimpleNamespace

import httpx

from tests.conftest import json_response, request_json_body, search_item, search_response
from tools import scrape_prices
from tools.scrape_prices import scrape_prices_batch, scrape_quantities_batch, snapshot_from_search_item


class FakeDb:
    """Just the Database surface the scrapers use."""

    def __init__(self, sets, products):
        self._sets, self._products = sets, products
        self.written = []
        self.quantities = {}

    def get_sets(self):
        return self._sets

    def get_products(self, **_):
        return self._products

    def insert_price_snapshots(self, snaps):
        self.written = list(snaps)
        return len(snaps), []

    def set_snapshot_quantity(self, product_id, snapshot_date, quantity):
        self.quantities[product_id] = quantity
        return 1


def use_mock_transport(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(
        scrape_prices.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )


def product(pid: str, tcg_id: int, name: str = "P") -> dict:
    return {"id": pid, "tcgplayer_product_id": tcg_id, "name": name, "set_id": "s1"}


def test_snapshot_keeps_zero_listings_and_median():
    snap = snapshot_from_search_item("p1", search_item(1, market=491.68, low=59.88, listings=0, median=600.0), "2026-09-30")
    assert snap.total_listings == 0
    assert snap.listed_median_price == 600.0
    assert snap.low_price == 59.88


def test_snapshot_none_without_any_price():
    assert snapshot_from_search_item("p1", search_item(1, market=None, low=None), "d") is None
    assert snapshot_from_search_item("p1", search_item(1, market=0, low=0), "d") is None


def test_snapshot_low_only_is_kept():
    snap = snapshot_from_search_item("p1", search_item(1, market=None, low=799.87), "d")
    assert snap.market_price is None and snap.low_price == 799.87


async def test_batch_matches_by_id_falls_back_and_reports_coverage(config, monkeypatch):
    sets = [{"id": "s1", "name": "151", "language": "en"}]
    db = FakeDb(sets, [product("p1", 101), product("p2", 102), product("p4", 104), product("p5", 105)])

    def handler(request):
        if request.url.host == "mp-search-api.tcgplayer.com":
            return json_response(search_response([
                search_item(101, market=20.0),
                search_item(999, market=5.0),            # not ours: ignored
                search_item(102, market=None, low=None),  # ours but no price at all
            ]))
        # fallback pricepoints
        if request.url.path.endswith("/104/pricepoints"):
            return json_response([{"printingType": "Normal", "marketPrice": 77.5, "listedMedianPrice": 80.0}])
        return json_response([{"printingType": "Normal", "marketPrice": None, "listedMedianPrice": None}])  # 105

    use_mock_transport(monkeypatch, handler)
    result = await scrape_prices_batch(db, config)

    written = {s.product_id: s for s in db.written}
    assert set(written) == {"p1", "p4"}
    assert written["p4"].market_price == 77.5          # priced via the pricepoints fallback
    assert result["fallback_priced"] == 1
    assert result["skipped"] == 2                       # p2 (no price in search) + p5 (no price in fallback)
    assert result["expected"] == 4
    assert result["coverage"] == 0.5
    assert sorted(result["unpriced_sample"]) == ["P", "P"]


async def test_batch_prices_a_product_once_even_if_two_sets_return_it(config, monkeypatch):
    sets = [{"id": "s1", "name": "A"}, {"id": "s2", "name": "B"}]
    db = FakeDb(sets, [product("p1", 101)])
    use_mock_transport(monkeypatch, lambda request: json_response(search_response([search_item(101)])))

    result = await scrape_prices_batch(db, config)

    assert len(db.written) == 1
    assert result["sets_processed"] == 2


async def test_batch_counts_failed_searches(config, monkeypatch):
    sets = [{"id": "s1", "name": "A"}, {"id": "s2", "name": "B"}]
    db = FakeDb(sets, [product("p1", 101)])

    def handler(request):
        if request.url.host == "mp-search-api.tcgplayer.com":
            return httpx.Response(503)
        return json_response([{"printingType": "Normal", "marketPrice": 10.0}])

    use_mock_transport(monkeypatch, handler)
    result = await scrape_prices_batch(db, config)

    assert result["queries_failed"] == 2
    assert result["sets_processed"] == 0
    assert result["fallback_priced"] == 1  # the product is still priced individually


async def test_batch_pages_generic_set_names(config, monkeypatch):
    sets = [{"id": "s1", "name": "Sword & Shield"}]
    # product 160 only appears on page 2 of the fuzzy search
    db = FakeDb(sets, [product("p1", 160)])

    def handler(request):
        start = request_json_body(request)["from"]
        items = [search_item(100 + i) for i in range(50)] if start == 0 else [search_item(150 + i) for i in range(20)]
        return json_response(search_response(items, total=70))

    use_mock_transport(monkeypatch, handler)
    result = await scrape_prices_batch(db, config)

    assert [s.product_id for s in db.written] == ["p1"]
    assert result["fallback_priced"] == 0


async def test_quantities_store_zero_but_not_failures(config, monkeypatch):
    db = FakeDb([], [product("p1", 101), product("p2", 102), product("p3", 103)])

    def handler(request):
        tcg_id = request.url.path.split("/")[-2]
        if tcg_id == "101":
            return json_response({"results": [{"totalResults": 2, "aggregations": {"quantity": [{"value": 3, "count": 2}]}}]})
        if tcg_id == "102":
            return json_response({"results": [{"totalResults": 0, "aggregations": {}}]})  # genuinely sold out
        return httpx.Response(500)

    use_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(scrape_prices.asyncio, "sleep", lambda _s: _noop())
    result = await scrape_quantities_batch(db, config, snapshot_date="2026-09-30")

    assert db.quantities == {"p1": 6, "p2": 0}   # p3 failed: nothing stored
    assert result["updated"] == 2
    assert result["failed"] == 1
    assert result["aborted"] is False


async def test_quantities_abort_when_blocked(config, monkeypatch):
    products = [product(f"p{i}", 100 + i) for i in range(40)]
    db = FakeDb([], products)
    use_mock_transport(monkeypatch, lambda request: httpx.Response(500))
    monkeypatch.setattr(scrape_prices.asyncio, "sleep", lambda _s: _noop())

    result = await scrape_quantities_batch(db, config, snapshot_date="2026-09-30")

    assert result["aborted"] is True
    assert result["failed"] == scrape_prices.MAX_CONSECUTIVE_QUANTITY_FAILURES
    assert db.quantities == {}


async def _noop():
    return None
