import json
from pathlib import Path

from clinic_siting.data_sources.google_places import parse_places
from clinic_siting.models import Place

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_searchtext_clinics():
    raw = json.loads((FIX / "places_searchtext_clinic.json").read_text(encoding="utf-8"))
    places = parse_places(raw)
    assert len(places) >= 1
    p = places[0]
    assert isinstance(p, Place)
    assert p.source == "google"
    assert p.lat is not None and p.lon is not None
    assert p.name != ""


def test_parse_searchnearby_pharmacy_has_rating_count():
    raw = json.loads((FIX / "places_searchnearby_pharmacy.json").read_text(encoding="utf-8"))
    places = parse_places(raw)
    assert any(p.rating_count is not None for p in places)


def test_parse_empty_response_returns_empty_list():
    # Places New v1 零結果回 {}
    assert parse_places({}) == []
