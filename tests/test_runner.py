import shutil
from pathlib import Path

from clinic_siting.runner import run_refresh

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


def test_run_refresh_offline_builds_site_and_returns_snapshot(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    site = tmp_path / "site"
    snap = run_refresh(live=False, reference_dir=ref, history_path=hist,
                       config_path=CONFIG, site_dir=site)
    assert set(snap["scores"].keys()) == SPECIALTIES
    assert hist.exists()
    assert (site / "data" / "history.json").exists()
    assert (site / "data" / "geo.json").exists()


def test_run_refresh_appends_each_run(tmp_path):
    ref = _make_reference_dir(tmp_path)
    hist = tmp_path / "history.jsonl"
    site = tmp_path / "site"
    run_refresh(live=False, reference_dir=ref, history_path=hist,
                config_path=CONFIG, site_dir=site)
    run_refresh(live=False, reference_dir=ref, history_path=hist,
                config_path=CONFIG, site_dir=site)
    lines = [l for l in hist.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
