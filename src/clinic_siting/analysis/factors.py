from __future__ import annotations

from dataclasses import dataclass

from clinic_siting.scoring.normalize import minmax_score

# 12 因子（順序對齊 config/specialties.yaml）
ALL_FACTORS = [
    "population_density",
    "age_gender",
    "day_night_gap",
    "purchasing_power",
    "business_density",
    "land_use_mix",
    "competition",
    "complementary_anchors",
    "convenience_density",
    "accessibility",
    "redevelopment_stage",
    "visibility",
]

NEUTRAL = 50.0

# 校準門檻（以龜山量級設定 lo/hi）
INCOME_LO, INCOME_HI = 350.0, 800.0          # 戶中位所得（千元）
POP_LO, POP_HI = 50_000.0, 300_000.0          # 區級人口
ANCHOR_LO, ANCHOR_HI = 0.0, 20.0              # 互補錨點家數
CONVENIENCE_LO, CONVENIENCE_HI = 0.0, 15.0    # 便利商店家數
BUSINESS_LO, BUSINESS_HI = 0.0, 100.0         # 商業 POI 計數（代理）
LANDUSE_LO, LANDUSE_HI = 1.0, 6.0             # 土地使用類型數
TRANSIT_LO, TRANSIT_HI = 0.0, 20.0            # 公車站數
DRIVE_MIN_LO, DRIVE_MIN_HI = 5.0, 30.0        # 車程分鐘（越短越好）

# 競爭需求/供給校準
VISIT_RATE = 0.02                              # 人口 → 月就診需求代理係數
DEMAND_PER_CLINIC_LO, DEMAND_PER_CLINIC_HI = 200.0, 800.0
NO_COMPETITION_SCORE = 70.0                    # 無同業：需求未滿足但缺群聚錨點


@dataclass
class FactorResult:
    score: float
    source: str  # real / degraded / manual / missing


def _competition_score(population, count) -> float:
    """同科別競爭：需求 vs 供給。需求>供給→群聚加分；過密才扣分。"""
    demand = population * VISIT_RATE
    if count == 0:
        return NO_COMPETITION_SCORE
    demand_per_clinic = demand / count
    return minmax_score(demand_per_clinic, DEMAND_PER_CLINIC_LO, DEMAND_PER_CLINIC_HI)


def _accessibility_score(transit_count, drive_time_min) -> float:
    transit = minmax_score(transit_count, TRANSIT_LO, TRANSIT_HI)
    if drive_time_min is None:
        return transit
    drive = minmax_score(drive_time_min, DRIVE_MIN_LO, DRIVE_MIN_HI, invert=True)
    return (transit + drive) / 2.0


def build_factors(raw: dict) -> dict[str, FactorResult]:
    """原始值 → 12 因子 FactorResult（已處理負向語意，分數一律高=佳）。"""
    out: dict[str, FactorResult] = {}

    def real_or_missing(key, scorer):
        if key in raw and raw[key] is not None:
            return FactorResult(scorer(raw[key]), "real")
        return FactorResult(NEUTRAL, "missing")

    # 本地離線來源（必有）
    out["purchasing_power"] = real_or_missing(
        "weighted_median_income",
        lambda v: minmax_score(v, INCOME_LO, INCOME_HI),
    )
    out["population_density"] = real_or_missing(
        "population",
        lambda v: minmax_score(v, POP_LO, POP_HI),
    )

    # 線上來源（缺漏 → missing，pipeline 層再決定是否沿用上次值）
    if "competition_count" in raw and raw["competition_count"] is not None:
        score = _competition_score(raw.get("population", 0), raw["competition_count"])
        out["competition"] = FactorResult(score, "real")
    else:
        out["competition"] = FactorResult(NEUTRAL, "missing")

    out["complementary_anchors"] = real_or_missing(
        "anchor_count",
        lambda v: minmax_score(v, ANCHOR_LO, ANCHOR_HI),
    )
    out["convenience_density"] = real_or_missing(
        "convenience_count",
        lambda v: minmax_score(v, CONVENIENCE_LO, CONVENIENCE_HI),
    )
    out["land_use_mix"] = real_or_missing(
        "landuse_types",
        lambda v: minmax_score(v, LANDUSE_LO, LANDUSE_HI),
    )

    if "transit_count" in raw and raw["transit_count"] is not None:
        score = _accessibility_score(raw["transit_count"], raw.get("drive_time_min"))
        out["accessibility"] = FactorResult(score, "real")
    else:
        out["accessibility"] = FactorResult(NEUTRAL, "missing")

    # 商業密度：OSM POI 計數代理，無全量營業稅籍 → 一律標 degraded
    if "business_count" in raw and raw["business_count"] is not None:
        score = minmax_score(raw["business_count"], BUSINESS_LO, BUSINESS_HI)
        out["business_density"] = FactorResult(score, "degraded")
    else:
        out["business_density"] = FactorResult(NEUTRAL, "missing")

    # 未下載資料 → 中性 missing
    out["age_gender"] = FactorResult(NEUTRAL, "missing")
    out["day_night_gap"] = FactorResult(NEUTRAL, "missing")

    # 手動因子 → 中性 manual（未來由介面覆寫）
    out["redevelopment_stage"] = FactorResult(NEUTRAL, "manual")
    out["visibility"] = FactorResult(NEUTRAL, "manual")

    return out


def factor_scores(factors: dict[str, FactorResult]) -> dict[str, float]:
    """抽出純分數 dict 餵給 scoring engine。"""
    return {name: r.score for name, r in factors.items()}
