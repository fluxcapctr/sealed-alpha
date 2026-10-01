from models import PokemonSet, Product


def test_set_upsert_payload_omits_unset_fields():
    payload = PokemonSet(name="151", code="sv3pt5").to_dict()
    assert payload == {"name": "151", "code": "sv3pt5", "language": "en"}


def test_set_upsert_payload_keeps_explicit_false_and_zero():
    payload = PokemonSet(name="Old", code="x", is_in_print=False, is_in_rotation=False, total_products=0).to_dict()
    assert payload["is_in_print"] is False
    assert payload["is_in_rotation"] is False
    assert payload["total_products"] == 0


def test_product_upsert_payload_does_not_reset_is_active_or_blank_fields():
    payload = Product(set_id="s", name="Box", product_type="Booster Box", tcgplayer_product_id=1).to_dict()
    for key in ("is_active", "msrp", "release_date", "tcgplayer_url", "image_url"):
        assert key not in payload
    assert payload["set_id"] == "s"


def test_product_can_still_be_deactivated_explicitly():
    assert Product(name="x", product_type="Other", is_active=False).to_dict()["is_active"] is False
