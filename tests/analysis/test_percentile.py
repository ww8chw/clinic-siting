import json
from site_siting.analysis.percentile import (
    Distribution, percentile_score, load_distribution, load_distributions)


def _dist(values):
    return Distribution(factor="x", unit="里", source="測試",
                        generated="2026-07-02", values=sorted(values))


def test_percentile_below_min_near_zero():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(5, d) == 0.0


def test_percentile_above_max_is_hundred():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(99, d) == 100.0


def test_percentile_midrank_of_median():
    # 5 值，query=30 在第 3 位：midrank=(2+3)/2=2.5 → 50
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(30, d) == 50.0


def test_percentile_invert_flips():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(10, d, invert=True) == 90.0


def test_percentile_empty_distribution_is_neutral():
    d = _dist([])
    assert percentile_score(42, d) == 50.0


def test_distribution_n_property():
    assert _dist([1, 2, 3]).n == 3


def test_load_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({
        "factor": "purchasing_power", "unit": "里", "source": "財政部",
        "generated": "2026-07-02", "values": [40, 10, 30]}), encoding="utf-8")
    d = load_distribution(p)
    assert d.factor == "purchasing_power"
    assert d.values == [10.0, 30.0, 40.0]   # 載入即排序


def test_load_distributions_keys_by_factor(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({
        "factor": "population_density", "unit": "區", "source": "s",
        "generated": "2026-07-02", "values": [1, 2]}), encoding="utf-8")
    got = load_distributions(tmp_path)
    assert set(got.keys()) == {"population_density"}


def test_load_distributions_missing_dir_returns_empty(tmp_path):
    assert load_distributions(tmp_path / "nope") == {}
