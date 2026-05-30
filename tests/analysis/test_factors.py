from clinic_siting.analysis.factors import (
    ALL_FACTORS,
    FactorResult,
    build_factors,
    factor_scores,
)

# 龜山量級的完整 raw 輸入
FULL_RAW = {
    "weighted_median_income": 600.0,   # 千元
    "population": 189052,
    "households": 87815,
    "competition_count": 5,
    "anchor_count": 8,
    "convenience_count": 6,
    "business_count": 40,
    "landuse_types": 4,
    "transit_count": 10,
    "drive_time_min": 12.0,
}


def test_build_factors_covers_all_twelve():
    f = build_factors(FULL_RAW)
    assert set(f.keys()) == set(ALL_FACTORS)
    assert len(ALL_FACTORS) == 12
    for r in f.values():
        assert isinstance(r, FactorResult)
        assert 0.0 <= r.score <= 100.0
        assert r.source in {"real", "degraded", "manual", "missing"}


def test_real_and_manual_sources():
    f = build_factors(FULL_RAW)
    assert f["purchasing_power"].source == "real"
    assert f["population_density"].source == "real"
    assert f["competition"].source == "real"
    assert f["business_density"].source == "degraded"   # OSM POI 代理
    assert f["age_gender"].source == "missing"
    assert f["day_night_gap"].source == "missing"
    assert f["redevelopment_stage"].source == "manual"
    assert f["visibility"].source == "manual"
    # 手動/缺漏因子皆中性 50
    for name in ("age_gender", "day_night_gap", "redevelopment_stage", "visibility"):
        assert f[name].score == 50.0


def test_missing_online_keys_degrade_to_neutral():
    raw = {"weighted_median_income": 600.0, "population": 189052}
    f = build_factors(raw)
    assert f["competition"].source == "missing"
    assert f["competition"].score == 50.0
    assert f["convenience_density"].source == "missing"
    assert f["convenience_density"].score == 50.0
    # 本地來源仍為 real
    assert f["purchasing_power"].source == "real"


def test_competition_cluster_beats_oversaturation():
    cluster = dict(FULL_RAW, competition_count=5)
    oversat = dict(FULL_RAW, competition_count=30)
    c = build_factors(cluster)["competition"].score
    o = build_factors(oversat)["competition"].score
    assert c > o


def test_factor_scores_returns_plain_floats():
    scores = factor_scores(build_factors(FULL_RAW))
    assert set(scores.keys()) == set(ALL_FACTORS)
    for v in scores.values():
        assert isinstance(v, float)


def test_deterministic():
    assert build_factors(FULL_RAW)["purchasing_power"].score == \
        build_factors(FULL_RAW)["purchasing_power"].score
