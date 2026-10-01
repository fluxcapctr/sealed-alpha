import httpx
import pytest

from tests.conftest import json_response, make_client, no_sleep, request_json_body, search_item, search_response
from tools import tcgplayer
from tools.tcgplayer import TcgPlayerError, clean_count, clean_price, fetch_listing_quantity, request_json, search_sealed


def test_clean_price_rejects_zero_negative_and_garbage():
    assert clean_price(491.68) == 491.68
    assert clean_price("12.345") == 12.35
    for bad in (None, 0, 0.0, -1, "n/a", float("nan"), float("inf")):
        assert clean_price(bad) is None


def test_clean_count_keeps_zero():
    assert clean_count(65.0) == 65
    assert clean_count(0) == 0
    assert clean_count(None) is None
    assert clean_count(-3) is None
    assert clean_count("x") is None


async def test_request_json_retries_503_then_succeeds(config):
    attempts = []

    def handler(request):
        attempts.append(1)
        return json_response({"ok": True}) if len(attempts) == 3 else httpx.Response(503)

    async with make_client(handler) as client:
        assert await request_json(client, "GET", "http://x/", config, sleep=no_sleep) == {"ok": True}
    assert len(attempts) == 3


async def test_request_json_honours_retry_after(config):
    waits = []

    async def record_sleep(seconds):
        waits.append(seconds)

    responses = iter([httpx.Response(429, headers={"Retry-After": "7"}), json_response({"ok": 1})])

    async with make_client(lambda request: next(responses)) as client:
        await request_json(client, "GET", "http://x/", config, sleep=record_sleep)
    assert waits == [7.0]


async def test_request_json_does_not_retry_404(config):
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(404)

    async with make_client(handler) as client:
        with pytest.raises(TcgPlayerError) as exc:
            await request_json(client, "GET", "http://x/", config, sleep=no_sleep)
    assert exc.value.status == 404
    assert len(attempts) == 1


async def test_request_json_gives_up_after_max_retries(config):
    attempts = []

    def handler(request):
        attempts.append(1)
        raise httpx.ConnectError("boom")

    async with make_client(handler) as client:
        with pytest.raises(TcgPlayerError, match="gave up"):
            await request_json(client, "GET", "http://x/", config, sleep=no_sleep)
    assert len(attempts) == config.max_retries


async def test_search_pages_until_total_and_dedupes(config):
    offsets = []

    def handler(request):
        body = request_json_body(request)
        offsets.append(body["from"])
        assert body["size"] == tcgplayer.PAGE_SIZE  # larger sizes are rejected by the API
        start = body["from"]
        count = min(50, 120 - start)
        items = [search_item(1000 + start + i) for i in range(count)]
        if start == 50:
            items[0] = search_item(1000)  # repeated across pages (unstable ordering)
        return json_response(search_response(items, total=120))

    async with make_client(handler) as client:
        result = await search_sealed(client, "Sword & Shield", "pokemon", config, sleep=no_sleep)

    assert offsets == [0, 50, 100]
    assert result.total == 120
    assert len(result.items) == 119  # one duplicate dropped
    assert result.truncated is True  # 119 < 120 reported


async def test_search_respects_max_pages(config):
    def handler(request):
        start = request_json_body(request)["from"]
        return json_response(search_response([search_item(start + i) for i in range(50)], total=500))

    async with make_client(handler) as client:
        result = await search_sealed(client, "x", "pokemon", config, max_pages=2, sleep=no_sleep)
    assert len(result.items) == 100
    assert result.truncated is True


async def test_search_keeps_partial_results_when_later_page_fails(config):
    def handler(request):
        if request_json_body(request)["from"] == 0:
            return json_response(search_response([search_item(i) for i in range(50)], total=100))
        return httpx.Response(500)

    async with make_client(handler) as client:
        result = await search_sealed(client, "x", "pokemon", config, sleep=no_sleep)
    assert len(result.items) == 50
    assert result.truncated is True


async def test_search_first_page_failure_raises(config):
    async with make_client(lambda request: httpx.Response(500)) as client:
        with pytest.raises(TcgPlayerError):
            await search_sealed(client, "x", "pokemon", config, sleep=no_sleep)


def listings_response(buckets, total):
    return {"results": [{"totalResults": total, "aggregations": {"quantity": buckets}, "results": []}]}


async def test_listing_quantity_sums_buckets(config):
    # Real response shape for the 151 ETB: 63 listings, 146 units
    buckets = [
        {"value": 1, "count": 49.0}, {"value": 2, "count": 6.0}, {"value": 3, "count": 2.0},
        {"value": 20, "count": 1.0}, {"value": 4, "count": 1.0}, {"value": 6, "count": 1.0},
        {"value": 25, "count": 1.0}, {"value": 14, "count": 1.0}, {"value": 10, "count": 1.0},
    ]
    async with make_client(lambda request: json_response(listings_response(buckets, 63))) as client:
        assert await fetch_listing_quantity(client, 503313, config, sleep=no_sleep) == 146


async def test_listing_quantity_zero_when_no_listings(config):
    async with make_client(lambda request: json_response(listings_response([], 0))) as client:
        assert await fetch_listing_quantity(client, 1, config, sleep=no_sleep) == 0


async def test_listing_quantity_unreadable_is_an_error_not_zero(config):
    async with make_client(lambda request: json_response(listings_response([], 12))) as client:
        with pytest.raises(TcgPlayerError):
            await fetch_listing_quantity(client, 1, config, sleep=no_sleep)


async def test_listing_quantity_http_failure_is_an_error_not_zero(config):
    async with make_client(lambda request: httpx.Response(500)) as client:
        with pytest.raises(TcgPlayerError):
            await fetch_listing_quantity(client, 1, config, sleep=no_sleep)
