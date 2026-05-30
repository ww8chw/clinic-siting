import json
from pathlib import Path

from clinic_siting.data_sources.google_distance import parse_distance

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "distance_matrix.json"


def test_parse_distance_returns_meters_and_seconds():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    results = parse_distance(raw)
    assert len(results) >= 1
    r = results[0]
    assert r["status"] == "OK"
    assert r["distance_m"] > 0
    assert r["duration_s"] > 0
    assert "公里" in r["distance_text"]


def test_parse_distance_handles_not_found_element():
    raw = {"rows": [{"elements": [{"status": "NOT_FOUND"}]}]}
    results = parse_distance(raw)
    assert results[0]["status"] == "NOT_FOUND"
    assert results[0]["distance_m"] is None
