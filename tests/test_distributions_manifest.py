from pathlib import Path
from site_siting.analysis.percentile import load_distributions

DIST_DIR = Path(__file__).resolve().parents[1] / "data" / "reference" / "distributions"


def test_committed_distributions_have_full_metadata():
    dists = load_distributions(DIST_DIR)
    # 至少已提交消費力與人口兩檔
    assert "purchasing_power" in dists
    assert "population_density" in dists
    for factor, d in dists.items():
        assert d.unit in {"里", "區"}, f"{factor} 單位異常"
        assert d.source, f"{factor} 缺出處"
        assert d.generated, f"{factor} 缺產生日期"
        assert d.n > 0, f"{factor} 母體為空"
        # values 排序遞增（load 時已排序）
        assert d.values == sorted(d.values)


def test_income_distribution_is_village_level():
    d = load_distributions(DIST_DIR)["purchasing_power"]
    assert d.unit == "里"
    assert d.n >= 100   # 全桃園數百里
