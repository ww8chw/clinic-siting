import json
from pathlib import Path

import pytest

from clinic_siting.data_sources.geocode import parse_geocode, SITE_LATLON, SITE_ADDRESS

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "geocode.json"


def test_parse_geocode_returns_latlon_and_address():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    lat, lon, formatted = parse_geocode(raw)
    assert 25.04 < lat < 25.05
    assert 121.39 < lon < 121.40
    assert "樂善二路503號" in formatted


def test_parse_geocode_raises_on_zero_results():
    with pytest.raises(ValueError):
        parse_geocode({"status": "ZERO_RESULTS", "results": []})


def test_site_constant_matches_known_point():
    assert abs(SITE_LATLON[0] - 25.0461974) < 1e-6
    assert "龜山" in SITE_ADDRESS
