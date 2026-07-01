from clinic_siting.analysis.factors import (
    ALL_FACTORS, build_factors, competition_pool_score)


def test_competition_aesthetic_removed():
    assert "competition_aesthetic" not in ALL_FACTORS
    assert "competition" in ALL_FACTORS
    assert len(ALL_FACTORS) == 13


def test_single_pool_matches_direct():
    # 單池：分數等同該池 count 的競爭分
    raw = {"population": 100000, "competition_pools": [{"count": 10, "weighted": 10}]}
    f = build_factors(raw)
    assert f["competition"].source == "real"
    assert f["competition"].score == competition_pool_score(100000, 10)


def test_multi_pool_takes_min():
    # 雙池：取最嚴格（最低分）。醫美池家數多 → 分數低 → 勝出
    raw = {"population": 100000, "competition_pools": [
        {"count": 3, "weighted": 3}, {"count": 30, "weighted": 30}]}
    f = build_factors(raw)
    expected = min(competition_pool_score(100000, 3),
                   competition_pool_score(100000, 30))
    assert f["competition"].score == expected


def test_no_pools_missing():
    f = build_factors({"population": 100000})
    assert f["competition"].source == "missing"
    assert f["competition"].score == 50.0
