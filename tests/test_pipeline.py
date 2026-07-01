import shutil
from pathlib import Path

from site_siting.pipeline import collect_offline, collect_industry, run_pipeline
from site_siting.scoring.config import IndustryProfile

FIX = Path(__file__).resolve().parent / "fixtures"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "industries.yaml"
MEDICAL = {
    "family_medicine", "functional_medicine", "weight_loss",
    "psychiatry", "aesthetics",
}
ALL_INDUSTRIES = MEDICAL | {
    "restaurant", "bubble_tea", "cafe", "gym", "cram_school", "hair_beauty",
}


def _make_reference_dir(tmp_path):
    ref = tmp_path / "reference"
    ref.mkdir()
    shutil.copy(FIX / "income_guishan_sample.csv", ref / "income_taoyuan.csv")
    shutil.copy(FIX / "population_taoyuan_sample.csv", ref / "population_taoyuan.csv")
    return ref


def test_collect_industry_builds_pools(monkeypatch):
    import site_siting.pipeline as pl

    def fake_scan_pool(center, pool, **kw):
        return [{"lat": 25.0, "lon": 121.0, "name": "x", "dist_km": 0.5}]

    def fake_scan_anchors(center, spec, **kw):
        return [{"lat": 25.0, "lon": 121.0, "name": "a", "dist_km": 0.3}]

    monkeypatch.setattr(pl, "scan_pool", fake_scan_pool)
    monkeypatch.setattr(pl, "scan_anchors", fake_scan_anchors)

    prof = IndustryProfile(
        id="bubble_tea", group="food", label="手搖飲",
        competitors=[{"source": "osm", "tags": {"amenity": "cafe"}}],
        anchors={"source": "osm", "tags": {"amenity": "school"}},
        weights={},
    )
    raw, geo = collect_industry((25.0, 121.0), prof)
    assert raw["competition_pools"][0]["count"] == 1
    assert raw["anchor_count"] == 1
    assert geo["competitors"] and geo["anchors"]


def test_collect_offline_has_local_keys(tmp_path):
    ref = _make_reference_dir(tmp_path)
    raw = collect_offline(ref)
    assert raw["population"] == 189052
    assert raw["households"] == 87815
    assert 406 <= raw["weighted_median_income"] <= 696


def test_run_pipeline_offline_new_schema(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    snap = run_pipeline(ref, hist, CONFIG, live=False)
    assert "location" in snap and "industries" in snap
    assert "factors" in snap["location"]
    assert set(snap["industries"].keys()) == ALL_INDUSTRIES
    fam = snap["industries"]["family_medicine"]
    assert fam["group"] == "medical"
    assert isinstance(fam["score"], float)
    # 完整 13 因子都在
    assert "competition" in fam["factors"]
    assert "population_density" in fam["factors"]
    # 離線時競爭缺漏 → 標 missing
    assert fam["factors"]["competition"]["source"] == "missing"
    # 地點因子區塊不含競爭/錨點
    assert "competition" not in snap["location"]["factors"]
    # 寫入一行
    assert hist.exists()
    assert len([l for l in hist.read_text().splitlines() if l.strip()]) == 1


def test_run_pipeline_offline_deterministic(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    s1 = run_pipeline(ref, hist, CONFIG, live=False)
    s2 = run_pipeline(ref, hist, CONFIG, live=False)
    scores1 = {i: d["score"] for i, d in s1["industries"].items()}
    scores2 = {i: d["score"] for i, d in s2["industries"].items()}
    assert scores1 == scores2
    # 兩次各寫一行
    assert len([l for l in hist.read_text().splitlines() if l.strip()]) == 2


def test_scores_are_bounded(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    snap = run_pipeline(ref, hist, CONFIG, live=False)
    for d in snap["industries"].values():
        assert 0.0 <= d["score"] <= 100.0


def test_offline_snapshot_has_empty_geo(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    snap = run_pipeline(ref, hist, CONFIG, live=False)
    for d in snap["industries"].values():
        assert d["geo"] == {}
