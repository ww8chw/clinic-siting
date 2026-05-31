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
CONVENIENCE_LO, CONVENIENCE_HI = 0.0, 25.0    # 便利商店家數（步行 1km）
BUSINESS_LO, BUSINESS_HI = 0.0, 40.0          # 商業 POI 計數（餐飲代理，步行 1km）
LANDUSE_LO, LANDUSE_HI = 1.0, 6.0             # 土地使用類型數
TRANSIT_LO, TRANSIT_HI = 0.0, 20.0            # 公車站數
DRIVE_MIN_LO, DRIVE_MIN_HI = 5.0, 30.0        # 車程分鐘（越短越好）
REDEV_AGE_LO, REDEV_AGE_HI = 0.0, 40.0        # 成交屋齡中位（年，越新越發展）

# 競爭需求/供給校準
VISIT_RATE = 0.02                              # 人口 → 月就診需求代理係數
DEMAND_PER_CLINIC_LO, DEMAND_PER_CLINIC_HI = 200.0, 800.0
NO_COMPETITION_SCORE = 70.0                    # 無同業：需求未滿足但缺群聚錨點

# 能見度：OSM 臨街道路 highway 等級 → 基礎分（越主要越顯眼）
HIGHWAY_VISIBILITY = {
    "motorway": 95.0, "trunk": 95.0,
    "primary": 90.0, "primary_link": 85.0,
    "secondary": 78.0, "secondary_link": 72.0,
    "tertiary": 62.0, "tertiary_link": 58.0,
    "unclassified": 48.0,
    "residential": 35.0,
    "living_street": 28.0,
    "service": 22.0,
}
HIGHWAY_DEFAULT = 40.0
LANE_BONUS = 6.0           # 每多 1 車道（>2）加分
LANE_BONUS_CAP_LANES = 4  # 最多計入 4 條額外車道


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


def road_visibility_score(highway: str, lanes) -> float:
    """單條臨街道路的能見度分：highway 等級基礎分 + 車道數加成，鎖 0–100。"""
    base = HIGHWAY_VISIBILITY.get(highway, HIGHWAY_DEFAULT)
    if lanes:
        extra = min(max(lanes - 2, 0), LANE_BONUS_CAP_LANES)
        base += extra * LANE_BONUS
    return max(0.0, min(100.0, base))


def best_road_visibility(roads: list[dict]) -> dict | None:
    """從周邊道路清單取能見度最高者：回傳 {name, highway, lanes, score}。
    空清單回 None。"""
    best = None
    for r in roads:
        score = road_visibility_score(r.get("highway", ""), r.get("lanes"))
        if best is None or score > best["score"]:
            best = {**r, "score": score}
    return best


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

    # 能見度：OSM 臨街道路等級代理；無道路資料 → 手動中性
    roads = raw.get("roads")
    best = best_road_visibility(roads) if roads else None
    if best is not None:
        out["visibility"] = FactorResult(best["score"], "real")
    else:
        out["visibility"] = FactorResult(NEUTRAL, "manual")

    # 重劃/發展階段：實價登錄區級成交屋齡中位（越新越發展）；無資料 → 手動中性
    if raw.get("building_age_median") is not None:
        score = minmax_score(raw["building_age_median"],
                             REDEV_AGE_LO, REDEV_AGE_HI, invert=True)
        out["redevelopment_stage"] = FactorResult(score, "degraded")
    else:
        out["redevelopment_stage"] = FactorResult(NEUTRAL, "manual")

    return out


def factor_scores(factors: dict[str, FactorResult]) -> dict[str, float]:
    """抽出純分數 dict 餵給 scoring engine。"""
    return {name: r.score for name, r in factors.items()}


def factor_explanation(name: str, raw: dict) -> dict:
    """回傳該因子的原始數據與換算依據文字：{raw, basis}。
    單一真相源——說明每個 0–100 分數背後量到什麼、用什麼門檻換算。"""
    g = raw.get

    if name == "purchasing_power":
        v = g("weighted_median_income")
        return {
            "raw": f"戶中位所得 {v:,.0f} 千元" if v is not None else "無資料",
            "basis": f"線性映射 {INCOME_LO:.0f}–{INCOME_HI:.0f} 千元 → 0–100",
        }
    if name == "population_density":
        v = g("population")
        vh = g("village_households")
        vp = g("village_population_est")
        village_txt = ""
        if vh is not None:
            village_txt = f"｜所在里 {vh:,.0f} 戶"
            if vp is not None:
                village_txt += f"、約 {vp:,.0f} 人（估）"
        return {
            "raw": (f"區人口 {v:,.0f} 人{village_txt}" if v is not None else "無資料"),
            "basis": (f"線性映射 {POP_LO:,.0f}–{POP_HI:,.0f} 人 → 0–100"
                      f"（里級戶數為財政部實數、人口按戶數比例估算）"),
        }
    if name == "competition":
        c = g("competition_count")
        if c is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        demand = (g("population") or 0) * VISIT_RATE
        per = demand / c if c else 0.0
        return {
            "raw": f"3km 內同業 {c} 家｜月需求估 {demand:,.0f} 人次（每家 {per:,.0f}）",
            "basis": (f"每家需求量映射 {DEMAND_PER_CLINIC_LO:.0f}–{DEMAND_PER_CLINIC_HI:.0f}"
                      f" → 0–100（需求>供給的群聚為加分，過密才扣分）"),
        }
    if name == "complementary_anchors":
        v = g("anchor_count")
        return {
            "raw": f"3km 內藥局/醫院 {v} 家" if v is not None else "無資料",
            "basis": f"線性映射 {ANCHOR_LO:.0f}–{ANCHOR_HI:.0f} 家 → 0–100",
        }
    if name == "convenience_density":
        v = g("convenience_count")
        return {
            "raw": f"1km 內超商 {v} 家" if v is not None else "無資料",
            "basis": f"線性映射 {CONVENIENCE_LO:.0f}–{CONVENIENCE_HI:.0f} 家 → 0–100",
        }
    if name == "business_density":
        v = g("business_count")
        return {
            "raw": f"1km 內餐飲 {v} 家（商業活動代理）" if v is not None else "無資料",
            "basis": (f"線性映射 {BUSINESS_LO:.0f}–{BUSINESS_HI:.0f} 家 → 0–100"
                      f"（OSM 代理、無全量稅籍，標 degraded）"),
        }
    if name == "land_use_mix":
        v = g("landuse_types")
        return {
            "raw": f"3km 內土地使用類型 {v} 種" if v is not None else "無資料",
            "basis": f"線性映射 {LANDUSE_LO:.0f}–{LANDUSE_HI:.0f} 種 → 0–100",
        }
    if name == "accessibility":
        t = g("transit_count")
        if t is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        d = g("drive_time_min")
        dtxt = f"｜車程 {d:.0f} 分" if d is not None else ""
        return {
            "raw": f"1km 內公車站 {t} 站{dtxt}",
            "basis": (f"公車站映射 0–{TRANSIT_HI:.0f} 站；車程 {DRIVE_MIN_LO:.0f}–"
                      f"{DRIVE_MIN_HI:.0f} 分（反向）取平均"),
        }
    if name == "visibility":
        roads = raw.get("roads")
        best = best_road_visibility(roads) if roads else None
        if best is None:
            return {"raw": "無臨街道路資料", "basis": "中性 50（待 OSM 道路或人工覆寫）"}
        lane_txt = f"、{best['lanes']} 車道" if best.get("lanes") else ""
        return {
            "raw": f"臨街主道「{best['name']}」({best['highway']}{lane_txt})",
            "basis": (f"OSM highway 等級基礎分 + 每增 1 車道(>2) +{LANE_BONUS:.0f}"
                      f"（取周邊最高等級道路）"),
        }
    if name in ("age_gender", "day_night_gap"):
        return {"raw": "尚無資料來源", "basis": "中性 50（待補單齡人口／晝夜信令）"}
    if name == "redevelopment_stage":
        v = g("building_age_median")
        if v is None:
            return {"raw": "待人工填入", "basis": "中性 50（手動因子，未來由介面覆寫）"}
        return {
            "raw": f"區內成交屋齡中位 {v:.0f} 年",
            "basis": (f"實價登錄屋齡映射 {REDEV_AGE_LO:.0f}–{REDEV_AGE_HI:.0f} 年（反向，"
                      f"越新越高）；區級代理標 degraded"),
        }
    return {"raw": "—", "basis": "—"}
