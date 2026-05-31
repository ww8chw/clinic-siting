import json
from pathlib import Path

from clinic_siting.scoring.config import load_specialty_config
from clinic_siting.site_export import (
    trend_series,
    factor_trend_series,
    latest_radar,
    latest_factor_table,
    specialty_breakdowns,
    build_payload,
    build_site,
)

CONFIG = load_specialty_config(
    Path(__file__).resolve().parents[1] / "config" / "specialties.yaml")

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
    "raw": {"weighted_median_income": 568.0, "population": 189052,
            "competition_count": 16},
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


def test_latest_factor_table_includes_raw_and_basis():
    rows = latest_factor_table([SNAP1, SNAP2])
    by_name = {r["factor"]: r for r in rows}
    assert by_name["competition"]["score"] == 30.0
    assert by_name["competition"]["source"] == "real"
    # 原始數據文字含實際家數
    assert "16 家" in by_name["competition"]["raw_text"]
    assert by_name["competition"]["basis_text"]
    # 消費力顯示中位所得
    assert "568" in by_name["purchasing_power"]["raw_text"]


def test_latest_factor_table_computes_delta():
    rows = latest_factor_table([SNAP1, SNAP2])
    by_name = {r["factor"]: r for r in rows}
    # competition 50 → 30：delta -20、-40%
    comp = by_name["competition"]
    assert comp["prev_score"] == 50.0
    assert comp["delta"] == -20.0
    assert comp["delta_pct"] == -40.0


def test_factor_table_delta_none_for_first_snapshot():
    rows = latest_factor_table([SNAP1])
    comp = {r["factor"]: r for r in rows}["competition"]
    assert comp["prev_score"] is None
    assert comp["delta"] is None
    assert comp["delta_pct"] is None


def test_factor_trend_series_aligns_dates():
    s = factor_trend_series([SNAP1, SNAP2])
    assert s["dates"] == ["2026-05-01", "2026-06-01"]
    assert s["factors"]["competition"] == [50.0, 30.0]
    assert s["factors"]["purchasing_power"] == [48.5, 49.0]


def test_specialty_breakdowns_sum_to_total():
    bd = specialty_breakdowns([SNAP2], CONFIG)
    assert set(bd.keys()) == {
        "family_medicine", "functional_medicine", "weight_loss",
        "psychiatry", "aesthetics",
    }
    fam = bd["family_medicine"]
    # 每列含權重等級與貢獻
    rows = {r["factor"]: r for r in fam["rows"]}
    assert rows["purchasing_power"]["level"] in {"最高", "高", "中", "低", "無"}
    # 貢獻加總 ≈ total
    assert abs(sum(r["contribution"] for r in fam["rows"]) - fam["total"]) < 0.05
    # purchasing_power 在 SNAP2 為 49 分、家醫權重「中」(3)；貢獻應為正
    assert rows["purchasing_power"]["contribution"] > 0


def test_specialty_breakdowns_empty_without_config():
    assert specialty_breakdowns([SNAP2], None) == {}


def test_build_payload_structure():
    p = build_payload([SNAP1, SNAP2], CONFIG)
    assert set(p.keys()) >= {
        "generated", "meta", "trend", "factor_trend", "radar",
        "factors", "breakdowns"}
    assert p["meta"]["address"]
    assert len(p["meta"]["latlon"]) == 2
    assert p["breakdowns"]["aesthetics"]["total"] >= 0


def test_build_site_writes_json(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text(
        json.dumps(SNAP1, ensure_ascii=False) + "\n" +
        json.dumps(SNAP2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    site = tmp_path / "site"
    build_site(hist, site, CONFIG)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert hjson["trend"]["dates"] == ["2026-05-01", "2026-06-01"]
    assert hjson["breakdowns"]["family_medicine"]["rows"]
    # geo.json 取最新一筆
    assert gjson["clinics"][0]["name"] == "A診所"


def test_build_site_handles_empty_history(tmp_path):
    hist = tmp_path / "history.jsonl"
    hist.write_text("", encoding="utf-8")
    site = tmp_path / "site"
    build_site(hist, site, CONFIG)
    hjson = json.loads((site / "data" / "history.json").read_text(encoding="utf-8"))
    assert hjson["trend"]["dates"] == []
    gjson = json.loads((site / "data" / "geo.json").read_text(encoding="utf-8"))
    assert gjson == {}
