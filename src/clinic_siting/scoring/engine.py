from clinic_siting.models import SpecialtyScore
from clinic_siting.scoring.config import SpecialtyConfig


def score_specialty(normalized_factors: dict[str, float],
                    weights: dict[str, int]) -> SpecialtyScore:
    """加權平均：Σ(分數×權重)/Σ(權重)，回傳 0–100。"""
    total_weight = sum(weights.values())
    if total_weight == 0:
        return SpecialtyScore(score=0.0, factor_contributions={})
    contributions = {
        factor: normalized_factors[factor] * weight / total_weight
        for factor, weight in weights.items()
    }
    return SpecialtyScore(
        score=sum(contributions.values()),
        factor_contributions=contributions,
    )


def score_all_specialties(normalized_factors: dict[str, float],
                          config: SpecialtyConfig) -> dict[str, SpecialtyScore]:
    results = {}
    for name, weights in config.specialties.items():
        s = score_specialty(normalized_factors, weights)
        s.specialty = name
        results[name] = s
    return results
