from models import Signal
from tools import compute_signals
from tools.compute_signals import compute_and_store_signals


class FakeDb:
    def __init__(self, previous=None):
        self.previous = previous or {}
        self.signals, self.alerts = [], []

    def get_previous_signals(self, before):
        return self.previous

    def upsert_signals(self, signals):
        self.signals = list(signals)
        return len(signals), []

    def create_alerts(self, alerts):
        self.alerts = list(alerts)
        return len(alerts)


def analytics(pid, price=10.0, change_7d=None):
    return {"product_id": pid, "product_name": f"Product {pid}", "current_price": price, "price_change_7d_pct": change_7d}


def test_hold_to_buy_crossing_raises_an_alert(monkeypatch):
    monkeypatch.setattr(
        compute_signals, "compute_signal",
        lambda a: Signal(product_id=a["product_id"], composite_score=45.0, recommendation="BUY"),
    )
    db = FakeDb(previous={"p1": {"recommendation": "HOLD", "composite_score": 5}})
    out = compute_and_store_signals(db, [analytics("p1")])
    assert [a.alert_type for a in db.alerts] == ["buy"]
    assert out["alerts"] == 1 and out["computed"] == 1


def test_no_crossing_alert_without_a_previous_signal(monkeypatch):
    monkeypatch.setattr(
        compute_signals, "compute_signal",
        lambda a: Signal(product_id=a["product_id"], composite_score=45.0, recommendation="BUY"),
    )
    db = FakeDb(previous={})
    compute_and_store_signals(db, [analytics("p1")])
    assert db.alerts == []


def test_unchanged_recommendation_does_not_alert(monkeypatch):
    monkeypatch.setattr(
        compute_signals, "compute_signal",
        lambda a: Signal(product_id=a["product_id"], composite_score=45.0, recommendation="BUY"),
    )
    db = FakeDb(previous={"p1": {"recommendation": "BUY", "composite_score": 40}})
    compute_and_store_signals(db, [analytics("p1")])
    assert db.alerts == []


def test_products_without_a_price_get_no_signal_and_price_drop_alerts_pass_through():
    db = FakeDb()
    out = compute_and_store_signals(db, [analytics("p1", price=None), analytics("p2", change_7d=-12.0)])
    assert [s.product_id for s in db.signals] == ["p2"]
    assert [a.alert_type for a in db.alerts] == ["price_drop"]
    assert out["computed"] == 1


def test_dry_run_writes_nothing():
    db = FakeDb()
    out = compute_and_store_signals(db, [analytics("p1", change_7d=20.0)], dry_run=True)
    assert db.signals == [] and db.alerts == []
    assert out["alerts"] == 1 and len(out["signals"]) == 1
