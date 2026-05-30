import json
from pathlib import Path

from clinic_siting.data_sources.osm_poi import parse_overpass, build_query
from clinic_siting.models import Place

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "overpass_convenience.json"


def test_parse_overpass_nodes():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    places = parse_overpass(raw)
    assert len(places) >= 1
    p = places[0]
    assert isinstance(p, Place)
    assert p.source == "osm"
    assert p.lat is not None and p.lon is not None


def test_parse_overpass_empty():
    assert parse_overpass({"elements": []}) == []


def test_build_query_contains_filter_and_radius():
    q = build_query("shop", "convenience", 25.04, 121.39, 1000)
    assert "convenience" in q
    assert "around:1000" in q
    assert "[out:json]" in q
