import json
from pathlib import Path

from clinic_siting.data_sources.tdx_transit import parse_bus_stops, TDX_TOKEN_URL
from clinic_siting.models import TransitStop

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "tdx_bus_stops.json"


def test_parse_bus_stops():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    stops = parse_bus_stops(raw)
    assert len(stops) >= 1
    s = stops[0]
    assert isinstance(s, TransitStop)
    assert s.kind == "bus"
    assert s.name != ""
    assert 25.0 < s.lat < 25.1
    assert 121.3 < s.lon < 121.5


def test_token_url_uses_tdxconnect_realm():
    # realm 必須是 TDXConnect（曾踩過 TDX realm 404 的坑）
    assert "TDXConnect" in TDX_TOKEN_URL


def test_parse_empty_list():
    assert parse_bus_stops([]) == []
