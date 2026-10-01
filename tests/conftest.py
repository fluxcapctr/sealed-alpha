"""Shared fixtures: a fast Config, a fake Supabase client, and an httpx mock-transport helper."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402


@pytest.fixture
def config(tmp_path) -> Config:
    """No real delays or backoff, and .tmp output goes to a temp dir."""
    return Config(
        tmp_dir=tmp_path,
        request_delay=0.0,
        retry_backoff_base=0.0,
        max_retries=3,
        supabase_url="http://localhost",
        supabase_service_role_key="test-key",
    )


async def no_sleep(_seconds: float) -> None:
    return None


def json_response(payload, status: int = 200, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers)


def request_json_body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode()) if request.content else {}


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def search_item(product_id: int, name: str = "Item", market=10.0, low=5.0, listings=3, median=9.0,
                set_name: str = "SV: Scarlet & Violet 151") -> dict:
    return {
        "productId": float(product_id),  # the API returns ids as floats
        "productName": name,
        "marketPrice": market,
        "lowestPrice": low,
        "medianPrice": median,
        "totalListings": float(listings) if listings is not None else None,
        "setName": set_name,
        "setId": 23237.0,
    }


def search_response(items: list[dict], total: int | None = None) -> dict:
    return {"errors": [], "results": [{"totalResults": total if total is not None else len(items), "results": items}]}


class FakeQuery:
    """Stands in for a supabase-py query builder: every chained call records itself and returns self."""

    def __init__(self, client: "FakeClient", table: str):
        self._client = client
        self.table = table
        self.calls: list[tuple] = []

    def __getattr__(self, name):
        def chain(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self
        return chain

    def execute(self):
        self._client.executed.append(self)
        return self._client.handler(self)

    def op(self) -> str | None:
        for name, _, _ in self.calls:
            if name in ("insert", "upsert", "update", "delete"):
                return name
        return "select"

    def arg(self, name: str):
        for call_name, args, kwargs in self.calls:
            if call_name == name:
                return args[0] if args else kwargs
        return None


class FakeClient:
    def __init__(self, handler=None):
        self.handler = handler or (lambda q: SimpleNamespace(data=[], count=0))
        self.executed: list[FakeQuery] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, name: str, params=None) -> FakeQuery:
        return FakeQuery(self, f"rpc:{name}")


def make_db(config: Config, handler=None):
    """A Database wired to a FakeClient (skips create_client)."""
    from db import Database

    db = Database.__new__(Database)
    db.config = config
    db.client = FakeClient(handler)
    return db
