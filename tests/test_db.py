from types import SimpleNamespace

from db import Database
from models import Alert, PriceSnapshot
from tests.conftest import FakeClient, make_db


def paged(rows):
    """Handler that serves `rows` for whatever .range(start, end) the query asked for."""
    def handler(query):
        rng = query.arg("range")
        if rng is None:
            return SimpleNamespace(data=rows)
        call = next(c for c in query.calls if c[0] == "range")
        start, end = call[1]
        return SimpleNamespace(data=rows[start:end + 1])
    return handler


def test_fetch_all_walks_every_page(config):
    rows = [{"id": i} for i in range(2500)]
    db = make_db(config, paged(rows))
    got = Database.fetch_all(lambda s, e: db.client.table("t").select("*").range(s, e))
    assert len(got) == 2500
    assert [q.calls[-1][1] for q in db.client.executed] == [(0, 999), (1000, 1999), (2000, 2999)]


def test_fetch_all_exact_multiple_of_page_size_terminates(config):
    rows = [{"id": i} for i in range(1000)]
    db = make_db(config, paged(rows))
    got = Database.fetch_all(lambda s, e: db.client.table("t").select("*").range(s, e))
    assert len(got) == 1000
    assert len(db.client.executed) == 2  # the second (empty) page proves there is nothing more


def test_get_product_analytics_is_paginated_and_ordered(config):
    rows = [{"product_id": str(i)} for i in range(1200)]
    db = make_db(config, paged(rows))
    assert len(db.get_product_analytics()) == 1200
    assert db.client.executed[0].arg("order") == "product_id"


def test_bulk_upsert_groups_rows_by_key_set(config):
    db = make_db(config)
    rows = [
        {"product_id": "a", "snapshot_date": "d", "market_price": 1.0},
        {"product_id": "b", "snapshot_date": "d", "market_price": 2.0, "low_price": 1.0},
        {"product_id": "c", "snapshot_date": "d", "market_price": 3.0},
    ]
    written, failed = db.bulk_upsert("price_snapshots", rows, on_conflict="product_id,snapshot_date")
    assert (written, failed) == (3, [])
    payloads = [q.arg("upsert") for q in db.client.executed]
    # mixed key sets are never sent together (would NULL the missing columns)
    assert sorted(len(p) for p in payloads) == [1, 2]
    assert all(len({tuple(sorted(r)) for r in p}) == 1 for p in payloads)


def test_bulk_upsert_isolates_a_bad_row(config):
    def handler(query):
        payload = query.arg("upsert")
        if isinstance(payload, list):
            raise RuntimeError("batch rejected")
        if payload["product_id"] == "bad":
            raise RuntimeError("constraint violation")
        return SimpleNamespace(data=[payload])

    db = make_db(config, handler)
    rows = [{"product_id": p, "snapshot_date": "d"} for p in ("a", "bad", "c")]
    written, failed = db.bulk_upsert("price_snapshots", rows, on_conflict="product_id,snapshot_date")
    assert written == 2
    assert [r["product_id"] for r in failed] == ["bad"]


def test_insert_price_snapshots_omits_unset_quantity(config):
    db = make_db(config)
    db.insert_price_snapshots([PriceSnapshot(product_id="a", snapshot_date="d", market_price=1.0)])
    sent = db.client.executed[0].arg("upsert")[0]
    assert "available_quantity" not in sent  # a rerun must not wipe a quantity written later


def test_create_alerts_skips_ones_already_raised_today_and_dupes(config):
    def handler(query):
        if query.table == "alerts" and query.op() == "select":
            return SimpleNamespace(data=[{"id": "1", "product_id": "p1", "alert_type": "price_drop"}])
        return SimpleNamespace(data=[])

    db = make_db(config, handler)
    created = db.create_alerts([
        Alert(product_id="p1", alert_type="price_drop", message="again"),   # already raised today
        Alert(product_id="p2", alert_type="price_drop", message="new"),
        Alert(product_id="p2", alert_type="price_drop", message="dupe in batch"),
        Alert(product_id="p1", alert_type="price_spike", message="different type"),
    ])
    assert created == 2
    inserted = [q.arg("insert") for q in db.client.executed if q.op() == "insert"][0]
    assert sorted((a["product_id"], a["alert_type"]) for a in inserted) == [("p1", "price_spike"), ("p2", "price_drop")]


def test_create_alerts_ignores_unique_violation_from_a_racing_run(config):
    def handler(query):
        if query.op() == "select":
            return SimpleNamespace(data=[])
        payload = query.arg("insert")
        if isinstance(payload, list):
            raise RuntimeError("batch failed")
        if payload["product_id"] == "p1":
            raise RuntimeError('duplicate key value violates unique constraint (code: 23505)')
        return SimpleNamespace(data=[payload])

    db = make_db(config, handler)
    assert db.create_alerts([Alert(product_id="p1", alert_type="price_drop"), Alert(product_id="p2", alert_type="price_drop")]) == 1


def test_get_previous_signals_keeps_newest_per_product(config):
    rows = [
        {"product_id": "a", "signal_date": "2026-09-29", "recommendation": "BUY", "composite_score": 40},
        {"product_id": "a", "signal_date": "2026-09-28", "recommendation": "HOLD", "composite_score": 0},
        {"product_id": "b", "signal_date": "2026-09-27", "recommendation": "SELL", "composite_score": -40},
    ]
    db = make_db(config, paged(rows))
    prev = db.get_previous_signals(before="2026-09-30")
    assert prev["a"]["recommendation"] == "BUY"
    assert prev["b"]["recommendation"] == "SELL"


def test_stats_use_exact_count_not_row_length(config):
    db = make_db(config, lambda q: SimpleNamespace(data=[{"id": 1}], count=4321))
    assert db.get_stats() == {"total_sets": 4321, "total_products": 4321, "total_snapshots": 4321}
