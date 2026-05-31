import json

from clinic_siting.site_export import (
    trend_series,
    latest_radar,
    latest_factor_bars,
    build_payload,
    build_site,
)

SNAP1 = {
    "date": "2026-05-01",
    "scores": {"family_medicine": 60.0, "aesthetics": 52.0},
    "factors": {
        "purchasing_power": {"score": 48.5, "source": "real"},
        "competition": {"score": 50.0, "source": "missing"},
    },
    "raw": {},
    "geo": {},
}
SNAP2 = {
    "date": "2026-06-01",
    "scores": {"family_medicine": 64.0, "aesthetics": 50.0},
    "factors": {
        "purchasing_power": {"score": 49.0, "source": "real"},
        "competition": {"score": 30.0, "source": "real"},
    },
    "raw": {},
    "geo": {"clinics": [{"lat": 25.05, "lon": 121.39, "name": "A診所"}]},
}


def test_trend_series_aligns_dates():
    s = trend_series([SNAP1, SNAP2])
    assert s["dates"] == ["2026-05-01", "2026-06-01"]
    assert s["specialties"]["family_medicine"] == [60.0, 64.0]
    assert s["specialties"]["aesthetics"] == [52.0, 50.0]


def test_latest_radar_uses_last_snapshot():
    r = latest_radar([SNAP1, SNAP2])
    assert "family_medicine" in r["labels"]
    idx = r["labels"].index("family_medicine")
    assert r["scores"][idx] == 64.0


def test_latest_factor_bars():
    bars = latest_factor_bars([SNAP1, SNAP2])
    by_name = {b["factor"]: b for b in bars}
    assert by_name["competition"]["score"] == 30.0
    assert by_name["competition"]["source"] == "real"


def test_build_payload_structure():
    p = build_payload([SNAP1, SNAP2])
    assert set(p.keys()) >= {"generated", "meta", "trend", "radar", "factors"}
    assert p["meta"]["address"]
    assert len(p["meta"]["latlon"]) == 2


def test_build_site_writes_json(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text(
        json.dumps(SNAP1, ensure_ascii=False) + "\n" +
        json.dumps(SNAP2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    build_site(hist, site)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert hjson["trend"]["dates"] == ["2026-05-01", "2026-06-01"]
    # geo.json 取最新一筆
    assert gjson["clinics"][0]["name"] == "A診所"


def test_build_site_handles_empty_history(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text("", encoding="utf-8")
    site = tmp_path / "site"
    build_site(hist, site)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    assert hjson["trend"]["dates"] == []
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert gjson == {}
