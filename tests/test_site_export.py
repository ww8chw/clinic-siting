import json
from pathlib import Path

from clinic_siting.scoring.config import load_industry_config
from clinic_siting.site_export import build_payload, build_site

CONFIG = load_industry_config(
    Path(__file__).resolve().parents[1] / "config" / "industries.yaml")


def _snap(date, fam_score):
    return {
        "date": date,
        "location": {"factors": {
            "population_density": {"score": 75.0, "source": "real"},
            "purchasing_power": {"score": 48.5, "source": "real"}},
            "raw": {"population": 180000, "weighted_median_income": 568.0}},
        "industries": {
            "family_medicine": {"group": "medical", "label": "家醫科",
                "score": fam_score,
                "factors": {"population_density": {"score": 75.0, "source": "real"},
                            "competition": {"score": 60.0, "source": "real"}},
                "raw": {"competition_pools": [{"count": 12, "weighted": 12}]},
                "geo": {"competitors": [{"lat": 25.05, "lon": 121.39, "name": "A診所"}]}},
            "bubble_tea": {"group": "food", "label": "手搖飲",
                "score": 55.0,
                "factors": {"population_density": {"score": 75.0, "source": "real"},
                            "competition": {"score": 50.0, "source": "real"}},
                "raw": {"competition_pools": [{"count": 20, "weighted": 20}]},
                "geo": {}},
        },
    }


def test_payload_groups_industries():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    assert "groups" in payload
    assert "medical" in payload["groups"]
    assert "family_medicine" in payload["groups"]["medical"]["industries"]
    assert "food" in payload["groups"]
    assert "bubble_tea" in payload["groups"]["food"]["industries"]


def test_payload_trend_per_industry():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    trend = payload["groups"]["medical"]["industries"]["family_medicine"]["trend"]
    assert trend == [70.0, 72.0]
    assert payload["dates"] == ["2026-06-01", "2026-07-01"]


def test_payload_meta_and_location_factors():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    assert payload["meta"]["address"]
    assert len(payload["meta"]["latlon"]) == 2
    # 地點因子共用區塊，不含競爭/錨點
    names = {r["factor"] for r in payload["location_factors"]}
    assert "population_density" in names
    assert "competition" not in names
    assert "complementary_anchors" not in names


def test_industry_factors_include_competition_and_delta():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    fam = payload["groups"]["medical"]["industries"]["family_medicine"]
    rows = {r["factor"]: r for r in fam["factors"]}
    # 行業因子含競爭
    assert "competition" in rows
    assert rows["competition"]["score"] == 60.0
    # 與上一筆相同（60→60）delta 0
    assert rows["competition"]["prev_score"] == 60.0
    assert rows["competition"]["delta"] == 0.0


def test_industry_breakdown_sums_to_total():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    fam = payload["groups"]["medical"]["industries"]["family_medicine"]
    bd = fam["breakdown"]
    assert bd is not None
    rows = {r["factor"]: r for r in bd["rows"]}
    assert rows["population_density"]["level"] in {"最高", "高", "中", "低", "無"}
    assert abs(sum(r["contribution"] for r in bd["rows"]) - bd["total"]) < 0.05


def test_build_site_writes_history_and_geo(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text(
        json.dumps(_snap("2026-06-01", 70.0), ensure_ascii=False) + "\n" +
        json.dumps(_snap("2026-07-01", 72.0), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    build_site(hist, site, CONFIG)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert hjson["dates"] == ["2026-06-01", "2026-07-01"]
    assert hjson["groups"]["medical"]["industries"]["family_medicine"]["trend"]
    # geo.json 依 industry id 分鍵，取最新一筆
    assert gjson["family_medicine"]["competitors"][0]["name"] == "A診所"
    assert gjson["bubble_tea"] == {}


def test_build_site_handles_empty_history(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text("", encoding="utf-8")
    site = tmp_path / "site"
    build_site(hist, site, CONFIG)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    assert hjson["dates"] == []
    assert hjson["groups"] == {}
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert gjson == {}
