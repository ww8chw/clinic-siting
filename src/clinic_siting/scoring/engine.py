from clinic_siting.models import SpecialtyScore
from clinic_siting.scoring.config import SpecialtyConfig


def score_specialty(normalized_factors: dict[str, float],
                    weights: dict[str, int]) -> SpecialtyScore:
    """加權平均：Σ(分數×權重)/Σ(權重)，回傳 0–100。

    contract：normalized_factors 必須包含 weights 內所有有權重的因子。
    缺漏因子時拋出 ValueError 並列出缺哪些；資料缺漏的降級（沿用上次快照值）
    應在 pipeline 層處理後，再餵給本引擎一組完整的因子分數。
    """
    missing = [f for f in weights if f not in normalized_factors]
    if missing:
        raise ValueError(f"normalized_factors 缺少因子: {sorted(missing)}")
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
