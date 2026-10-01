import sys
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from tests.conftest import make_db
from tools import send_drip_emails as drip


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(drip.time, "sleep", lambda _s: None)


class FakeResend:
    def __init__(self, fail_for=()):
        self.sent, self.fail_for, self.api_key = [], set(fail_for), None
        self.Emails = SimpleNamespace(send=self._send)

    def _send(self, params):
        if params["to"] in self.fail_for:
            raise RuntimeError("provider rejected")
        self.sent.append(params)
        return {"id": f"re_{len(self.sent)}"}


def sub(i, step=0, token="11111111-1111-1111-1111-111111111111"):
    return {
        "id": f"s{i}", "email": f"u{i}@example.com", "current_step": step,
        "next_send_date": str(date.today()), "unsubscribe_token": token, "opted_out": False,
    }


def make_drip_db(config, subscribers, claim_ok=True):
    """Fake DB: select -> subscribers; update (the claim/release) -> rows iff claim_ok; insert (log) -> ok."""
    def handler(query):
        if query.table == "drip_subscribers" and query.op() == "select":
            return SimpleNamespace(data=list(subscribers))
        if query.table == "drip_subscribers" and query.op() == "update":
            return SimpleNamespace(data=[{"id": "x"}] if claim_ok else [])
        return SimpleNamespace(data=[])
    return make_db(config, handler)


def writes(db, table, op):
    return [q for q in db.client.executed if q.table == table and q.op() == op]


def test_claims_before_sending_and_sends_unsubscribe_headers(config, monkeypatch):
    fake = FakeResend()
    monkeypatch.setitem(sys.modules, "resend", fake)
    config.resend_api_key = "key"
    db = make_drip_db(config, [sub(1)])

    result = drip.send_drip_emails(db, config)

    assert result["sent"] == 1 and result["failed"] == 0
    # claim (update) happened before the log insert, and the email carries the one-click headers
    ops = [q.op() for q in db.client.executed if q.table != "drip_subscribers" or q.op() != "select"]
    assert ops == ["update", "insert"]
    headers = fake.sent[0]["headers"]
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/api/unsubscribe?token=11111111" in headers["List-Unsubscribe"]
    claim = writes(db, "drip_subscribers", "update")[0].arg("update")
    assert claim["current_step"] == 1
    assert claim["next_send_date"] == str(date.today() + timedelta(days=drip.DRIP_SCHEDULE[1]))


def test_failed_send_releases_the_claim(config, monkeypatch):
    fake = FakeResend(fail_for={"u1@example.com"})
    monkeypatch.setitem(sys.modules, "resend", fake)
    config.resend_api_key = "key"
    db = make_drip_db(config, [sub(1, step=2)])

    result = drip.send_drip_emails(db, config)

    assert result["sent"] == 0 and result["failed"] == 1
    claim, release = [q.arg("update") for q in writes(db, "drip_subscribers", "update")]
    assert claim["current_step"] == 3
    assert release["current_step"] == 2           # put back so tomorrow's run retries step 3
    assert writes(db, "drip_log", "insert") == []


def test_lost_claim_race_sends_nothing(config, monkeypatch):
    fake = FakeResend()
    monkeypatch.setitem(sys.modules, "resend", fake)
    config.resend_api_key = "key"
    db = make_drip_db(config, [sub(1)], claim_ok=False)

    result = drip.send_drip_emails(db, config)

    assert fake.sent == []
    assert result["skipped"] == 1 and result["sent"] == 0


def test_log_failure_does_not_unsend_or_double_send(config, monkeypatch):
    fake = FakeResend()
    monkeypatch.setitem(sys.modules, "resend", fake)
    config.resend_api_key = "key"

    def handler(query):
        if query.op() == "select":
            return SimpleNamespace(data=[sub(1)])
        if query.table == "drip_log":
            raise RuntimeError("db down")
        return SimpleNamespace(data=[{"id": "x"}])

    db = make_db(config, handler)
    result = drip.send_drip_emails(db, config)
    assert result["sent"] == 1 and result["failed"] == 0
    assert len(writes(db, "drip_subscribers", "update")) == 1  # claimed once, never released


def test_missing_unsubscribe_token_blocks_the_send(config, monkeypatch):
    fake = FakeResend()
    monkeypatch.setitem(sys.modules, "resend", fake)
    config.resend_api_key = "key"
    db = make_drip_db(config, [sub(1, token=None)])
    result = drip.send_drip_emails(db, config)
    assert fake.sent == [] and result["skipped"] == 1


def test_dry_run_neither_sends_nor_claims(config, monkeypatch):
    fake = FakeResend()
    monkeypatch.setitem(sys.modules, "resend", fake)
    db = make_drip_db(config, [sub(1)])
    result = drip.send_drip_emails(db, config, dry_run=True)
    assert result["sent"] == 1
    assert fake.sent == [] and writes(db, "drip_subscribers", "update") == []


def test_empty_sender_secret_falls_back_to_default(monkeypatch):
    from config import Config
    monkeypatch.setenv("DRIP_SENDER_EMAIL", "")   # what CI passes for an unset secret
    monkeypatch.setenv("WHOLESALE_URL", "  ")
    cfg = Config()
    assert cfg.drip_sender_email == "onboarding@resend.dev"
    assert cfg.wholesale_url == "https://kitakamicards.com"
