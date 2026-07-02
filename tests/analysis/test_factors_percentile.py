from site_siting.analysis.percentile import Distribution
from site_siting.analysis.factors import build_factors, factor_explanation


def _dist(factor, unit, values):
    return Distribution(factor=factor, unit=unit, source="測試",
                        generated="2026-07-02", values=sorted(values))


DIST = {
    "purchasing_power": _dist("purchasing_power", "里", [400, 500, 600, 700, 800]),
    "population_density": _dist("population_density", "區", [50000, 100000, 200000, 300000]),
}
RAW = {"weighted_median_income": 700.0, "population": 200000}


def test_percentile_used_when_distribution_present():
    # 700 在 [400..800] 第 4 位 midrank=(3+4)/2=3.5 → 70
    f = build_factors(RAW, dist=DIST)
    assert f["purchasing_power"].score == 70.0
    assert f["purchasing_power"].source == "real"


def test_minmax_fallback_without_distribution():
    # 無 dist → 沿用舊 minmax（700 對 350–800 → (700-350)/450*100 ≈ 77.8）
    f = build_factors(RAW)
    assert abs(f["purchasing_power"].score - 77.78) < 0.1


def test_population_percentile():
    # 200000 在 [50k,100k,200k,300k] midrank=(2+3)/2=2.5 → 62.5
    f = build_factors(RAW, dist=DIST)
    assert f["population_density"].score == 62.5


def test_explanation_shows_percentile_and_n():
    exp = factor_explanation("purchasing_power", RAW, dist=DIST)
    assert "百分位" in exp["basis"]
    assert "5" in exp["basis"]   # N=5


def test_explanation_falls_back_without_dist():
    exp = factor_explanation("purchasing_power", RAW)
    assert "線性映射" in exp["basis"]


def test_building_age_percentile_inverts():
    d = _dist("redevelopment_stage", "區", [5, 10, 20, 30, 40])
    raw = {"building_age_median": 10.0}
    f = build_factors(raw, dist={"redevelopment_stage": d})
    # 10 在第2位 midrank=(1+2)/2=1.5 → pctl 30 → invert 70
    assert f["redevelopment_stage"].score == 70.0
    assert f["redevelopment_stage"].source == "degraded"


def test_age_gender_composite_percentile():
    dp = _dist("age_prime", "里", [0.30, 0.35, 0.40, 0.45, 0.50])
    df = _dist("age_female", "里", [0.46, 0.48, 0.50, 0.52, 0.54])
    raw = {"age_prime_share": 0.45, "female_share": 0.52}
    f = build_factors(raw, dist={"age_prime": dp, "age_female": df})
    # 壯年 0.45 midrank=(3+4)/2=3.5→70；女 0.52 →70；0.7*70+0.3*70=70
    assert f["age_gender"].score == 70.0
    assert f["age_gender"].source == "real"
