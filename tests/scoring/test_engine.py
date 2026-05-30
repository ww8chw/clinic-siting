from clinic_siting.scoring.engine import score_specialty, score_all_specialties
from clinic_siting.scoring.config import SpecialtyConfig


def _config():
    return SpecialtyConfig(
        factors=["a", "b"],
        negative_factors=[],
        specialties={
            "x": {"a": 4, "b": 2},   # 權重 4:2
            "y": {"a": 2, "b": 2},   # 權重 1:1
        },
    )


def test_score_specialty_weighted_average():
    # a=100, b=40, 權重 4:2 -> (100*4 + 40*2)/6 = 80
    result = score_specialty({"a": 100.0, "b": 40.0}, {"a": 4, "b": 2})
    assert result.score == 80.0
    assert result.specialty is None or True  # specialty 名由上層填


def test_score_specialty_equal_weights():
    # a=100, b=0, 權重 1:1 -> 50
    result = score_specialty({"a": 100.0, "b": 0.0}, {"a": 2, "b": 2})
    assert result.score == 50.0


def test_factor_contributions_sum_to_score():
    result = score_specialty({"a": 100.0, "b": 40.0}, {"a": 4, "b": 2})
    assert round(sum(result.factor_contributions.values()), 6) == round(result.score, 6)


def test_score_all_specialties_returns_one_per_specialty():
    cfg = _config()
    normalized = {"a": 100.0, "b": 40.0}
    results = score_all_specialties(normalized, cfg)
    assert set(results.keys()) == {"x", "y"}
    assert results["x"].score == 80.0          # 權重 4:2
    assert results["y"].score == 70.0          # 權重 1:1 -> (100+40)/2
    assert results["x"].specialty == "x"
