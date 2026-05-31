from clinic_siting.analysis.factors import (
    ALL_FACTORS,
    FactorResult,
    build_factors,
    factor_scores,
    road_visibility_score,
    best_road_visibility,
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


def test_competition_uses_weighted_effective_count():
    # 同樣 10 家，但距離加權後有效家數僅 4 → 競爭較輕、分數較高
    base = dict(FULL_RAW, competition_count=10)
    weighted = dict(base, competition_weighted=4.0)
    s_raw = build_factors(base)["competition"].score
    s_w = build_factors(weighted)["competition"].score
    assert s_w > s_raw
    assert build_factors(weighted)["competition"].source == "real"


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


def test_road_visibility_higher_class_scores_higher():
    # 主要道路 > 次要 > 巷弄
    assert road_visibility_score("primary", None) > \
        road_visibility_score("tertiary", None)
    assert road_visibility_score("tertiary", None) > \
        road_visibility_score("residential", None)


def test_road_visibility_lanes_add_bonus():
    assert road_visibility_score("unclassified", 4) > \
        road_visibility_score("unclassified", 2)
    # 分數鎖在 0–100
    assert 0.0 <= road_visibility_score("motorway", 8) <= 100.0


def test_best_road_visibility_picks_max():
    roads = [
        {"name": "郵園路", "highway": "residential", "lanes": None},
        {"name": "樂善二路", "highway": "unclassified", "lanes": 4},
        {"name": "文桃路", "highway": "tertiary", "lanes": 2},
    ]
    best = best_road_visibility(roads)
    # 文桃路 tertiary 應勝出，分數高於人工中性 50
    assert best["name"] == "文桃路"
    assert best["score"] > 50.0


def test_best_road_visibility_empty_returns_none():
    assert best_road_visibility([]) is None


def test_visibility_factor_real_when_roads_present():
    raw = dict(FULL_RAW, roads=[
        {"name": "文桃路", "highway": "tertiary", "lanes": 2}])
    f = build_factors(raw)
    assert f["visibility"].source == "real"
    assert f["visibility"].score > 50.0


def test_visibility_factor_manual_without_roads():
    f = build_factors(FULL_RAW)
    assert f["visibility"].source == "manual"
    assert f["visibility"].score == 50.0


def test_redevelopment_from_building_age():
    young = dict(FULL_RAW, building_age_median=5.0)
    old = dict(FULL_RAW, building_age_median=35.0)
    fy = build_factors(young)["redevelopment_stage"]
    fo = build_factors(old)["redevelopment_stage"]
    # 屋齡越新 → 重劃/發展分越高
    assert fy.score > fo.score
    assert fy.source == "degraded"   # 區級實價登錄代理


def test_redevelopment_manual_without_building_age():
    f = build_factors(FULL_RAW)["redevelopment_stage"]
    assert f.source == "manual"
    assert f.score == 50.0
