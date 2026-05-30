import shutil
from pathlib import Path

from clinic_siting.pipeline import collect_offline, run_pipeline

FIX = Path(__file__).resolve().parent / "fixtures"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "specialties.yaml"
SPECIALTIES = {
    "family_medicine", "functional_medicine", "weight_loss",
    "psychiatry", "aesthetics",
}


def _make_reference_dir(tmp_path):
    ref = tmp_path / "reference"
    ref.mkdir()
    shutil.copy(FIX / "income_guishan_sample.csv", ref / "income_taoyuan.csv")
    shutil.copy(FIX / "population_taoyuan_sample.csv", ref / "population_taoyuan.csv")
    return ref


def test_collect_offline_has_local_keys(tmp_path):
    ref = _make_reference_dir(tmp_path)
    raw = collect_offline(ref)
    assert raw["population"] == 189052
    assert raw["households"] == 87815
    assert 406 <= raw["weighted_median_income"] <= 696


def test_run_pipeline_offline_outputs_full_snapshot(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    snap = run_pipeline(ref, hist, CONFIG, live=False)
    assert set(snap["scores"].keys()) == SPECIALTIES
    assert len(snap["factors"]) == 12
    assert "weighted_median_income" in snap["raw"]
    # 離線時線上因子缺漏 → 標 missing/中性
    assert snap["factors"]["competition"]["source"] == "missing"
    # 寫入一行
    assert hist.exists()
    assert len([l for l in hist.read_text().splitlines() if l.strip()]) == 1


def test_run_pipeline_offline_deterministic(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    s1 = run_pipeline(ref, hist, CONFIG, live=False)
    s2 = run_pipeline(ref, hist, CONFIG, live=False)
    assert s1["scores"] == s2["scores"]
    # 兩次各寫一行
    assert len([l for l in hist.read_text().splitlines() if l.strip()]) == 2


def test_scores_are_bounded(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    snap = run_pipeline(ref, hist, CONFIG, live=False)
    for v in snap["scores"].values():
        assert 0.0 <= v <= 100.0
