from types import SimpleNamespace

import pytest

from tests.conftest import search_item
from tools import seed_products
from tools.seed_products import item_belongs_to_set, seed_products_for_set


@pytest.mark.parametrize("our_name,tcg_name,expected", [
    ("151", "SV: Scarlet & Violet 151", True),
    ("Paldea Evolved", "SV02: Paldea Evolved", True),
    ("Paldea Evolved", "SV: Paldean Fates", False),          # fuzzy neighbour
    ("Crown Zenith", "SWSH: Crown Zenith", True),
    ("Pokémon GO", "SWSH10.5: Pokemon GO", True),              # accents folded
    ("151", "SV01: Scarlet & Violet Base Set", False),
    ("Evolving Skies", "Miscellaneous Cards & Products", False),
    ("", "Anything", False),
])
def test_item_belongs_to_set(our_name, tcg_name, expected):
    assert item_belongs_to_set({"setName": tcg_name}, our_name) is expected


def test_numeric_names_match_whole_words_only():
    assert item_belongs_to_set({"setName": "SV: Scarlet & Violet 151"}, "15") is False


class FakeDb:
    def __init__(self, existing=None):
        self.existing = existing or {}
        self.upserted = []

    def get_existing_products_by_tcgplayer_ids(self, ids):
        return {i: self.existing[i] for i in ids if i in self.existing}

    def upsert_product(self, product):
        self.upserted.append(product)


def run(monkeypatch, config, items, db, **kwargs):
    async def fake_search(*_a, **_k):
        return items
    monkeypatch.setattr(seed_products, "search_tcgplayer_products", fake_search)
    set_data = {"id": "set-151", "name": "151", "release_date": "2023-09-22"}
    return seed_products_for_set(set_data, db, config, **kwargs)


def item(pid, name, set_name="SV: Scarlet & Violet 151"):
    d = search_item(pid, name, set_name=set_name)
    d["productUrlName"] = name.lower().replace(" ", "-")
    return d


async def test_other_sets_results_are_not_attached_to_this_set(config, monkeypatch):
    db = FakeDb()
    items = [
        item(1, "151 Booster Box"),
        item(2, "Paldean Fates Booster Bundle", set_name="SV: Paldean Fates"),
    ]
    result = await run(monkeypatch, config, items, db)
    assert [p.tcgplayer_product_id for p in db.upserted] == [1]
    assert result["other_set"] == 1 and result["seeded"] == 1


async def test_existing_products_are_never_moved_between_sets(config, monkeypatch):
    db = FakeDb(existing={1: {"id": "p1", "set_id": "some-other-set", "tcgplayer_product_id": 1}})
    result = await run(monkeypatch, config, [item(1, "151 Booster Box")], db)
    assert db.upserted == []
    assert result["existing"] == 1 and result["seeded"] == 0


async def test_update_existing_refreshes_but_keeps_the_set(config, monkeypatch):
    db = FakeDb(existing={1: {"id": "p1", "set_id": "some-other-set", "tcgplayer_product_id": 1}})
    await run(monkeypatch, config, [item(1, "151 Booster Box")], db, update_existing=True)
    assert len(db.upserted) == 1
    assert "set_id" not in db.upserted[0].to_dict()


async def test_unassigned_existing_product_gets_the_set(config, monkeypatch):
    db = FakeDb(existing={1: {"id": "p1", "set_id": None, "tcgplayer_product_id": 1}})
    await run(monkeypatch, config, [item(1, "151 Booster Box")], db)
    assert db.upserted[0].set_id == "set-151"


async def test_new_products_inherit_the_set_release_date_and_are_not_forced_active(config, monkeypatch):
    db = FakeDb()
    await run(monkeypatch, config, [item(1, "151 Booster Box")], db)
    payload = db.upserted[0].to_dict()
    assert payload["release_date"] == "2023-09-22"
    assert "is_active" not in payload


async def test_no_set_check_accepts_everything(config, monkeypatch):
    db = FakeDb()
    items = [item(2, "Paldean Fates Booster Bundle", set_name="SV: Paldean Fates")]
    await run(monkeypatch, config, items, db, check_set=False)
    assert len(db.upserted) == 1


async def test_other_types_and_half_boxes_are_skipped_for_english(config, monkeypatch):
    db = FakeDb()
    items = [item(1, "151 Sticker Sheet"), item(2, "151 Half Booster Box"), item(3, "151 Elite Trainer Box")]
    result = await run(monkeypatch, config, items, db)
    assert [p.tcgplayer_product_id for p in db.upserted] == [3]
    assert result["skipped"] == 2
