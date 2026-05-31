from __future__ import annotations

import math
from dataclasses import dataclass

from clinic_siting.analysis.aggregate import WALK_KM, DRIVE_KM, COMPETITION_FLOOR
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
ANCHOR_LO, ANCHOR_HI = 0.0, 10.0              # 互補錨點距離加權有效家數
CONVENIENCE_LO, CONVENIENCE_HI = 0.0, 25.0    # 便利商店家數（步行 1km）
BUSINESS_LO, BUSINESS_HI = 0.0, 40.0          # 商業 POI 計數（餐飲代理，步行 1km）
LANDUSE_LO, LANDUSE_HI = 1.0, 6.0             # 土地使用類型數
TRANSIT_LO, TRANSIT_HI = 0.0, 20.0            # 公車站數
DRIVE_MIN_LO, DRIVE_MIN_HI = 5.0, 30.0        # 車程分鐘（越短越好）
REDEV_AGE_LO, REDEV_AGE_HI = 0.0, 40.0        # 成交屋齡中位（年，越新越發展）

# 年齡/性別：壯年(25–49)占比 + 女性占比 → 自費客群 favorability
AGE_PRIME_LO, AGE_PRIME_HI = 0.30, 0.55       # 壯年占比（典型區約 0.38）
FEMALE_LO, FEMALE_HI = 0.45, 0.55             # 女性占比（中心 0.50）
AGE_PRIME_WEIGHT = 0.7                         # 壯年:女性 = 7:3

# 晝夜落差：營業家數每千人相對全國比值，越接近 1（日夜均衡）越佳
DAYNIGHT_K = 70.0                              # 每偏離 |ln(比值)| 的扣分係數

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


def age_gender_score(prime_share: float, female_share: float) -> float:
    """壯年(25–49)占比為主、女性占比為輔，加權成自費客群 favorability。"""
    age_c = minmax_score(prime_share, AGE_PRIME_LO, AGE_PRIME_HI)
    fem_c = minmax_score(female_share, FEMALE_LO, FEMALE_HI)
    return AGE_PRIME_WEIGHT * age_c + (1.0 - AGE_PRIME_WEIGHT) * fem_c


def day_night_score(ratio: float) -> float:
    """營業家數每千人相對全國比值 → 分數；比值=1（日夜均衡）最高，兩端遞減。"""
    if ratio <= 0:
        return NEUTRAL
    score = 100.0 - DAYNIGHT_K * abs(math.log(ratio))
    return max(0.0, min(100.0, score))


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
    # 優先用距離加權有效家數（近者競爭強）；無則退回原始家數
    comp = raw.get("competition_weighted")
    if comp is None:
        comp = raw.get("competition_count")
    if comp is not None:
        score = _competition_score(raw.get("population", 0), comp)
        out["competition"] = FactorResult(score, "real")
    else:
        out["competition"] = FactorResult(NEUTRAL, "missing")

    # 互補錨點：優先用距離加權有效家數（近者綜效強）；無則退回原始家數
    anchor = raw.get("anchor_weighted")
    if anchor is None:
        anchor = raw.get("anchor_count")
    if anchor is not None:
        out["complementary_anchors"] = FactorResult(
            minmax_score(anchor, ANCHOR_LO, ANCHOR_HI), "real")
    else:
        out["complementary_anchors"] = FactorResult(NEUTRAL, "missing")
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

    # 年齡/性別：村里壯年(25–49)占比 + 女性占比（內政部 ODRP052）
    if raw.get("age_prime_share") is not None and raw.get("female_share") is not None:
        out["age_gender"] = FactorResult(
            age_gender_score(raw["age_prime_share"], raw["female_share"]), "real")
    else:
        out["age_gender"] = FactorResult(NEUTRAL, "missing")

    # 晝夜落差：行政區營業家數每千人相對全國比值（財政部稅籍登記）
    if raw.get("business_ratio") is not None:
        out["day_night_gap"] = FactorResult(
            day_night_score(raw["business_ratio"]), "real")
    else:
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
        w = g("competition_weighted")
        eff = w if w is not None else c
        demand = (g("population") or 0) * VISIT_RATE
        per = demand / eff if eff else 0.0
        eff_txt = f"（距離加權有效 {w:.1f} 家）" if w is not None else ""
        return {
            "raw": (f"3km 內同業 {c} 家{eff_txt}｜月需求估 {demand:,.0f} 人次"
                    f"（每家 {per:,.0f}）"),
            "basis": (f"近者競爭強：步行 {WALK_KM:.0f}km 內權重 1.0，至車程 "
                      f"{DRIVE_KM:.0f}km 線性衰減至 {COMPETITION_FLOOR}；有效家數映射 "
                      f"{DEMAND_PER_CLINIC_LO:.0f}–{DEMAND_PER_CLINIC_HI:.0f} → 0–100"),
        }
    if name == "complementary_anchors":
        v = g("anchor_count")
        if v is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        w = g("anchor_weighted")
        eff_txt = f"（距離加權有效 {w:.1f} 家）" if w is not None else ""
        return {
            "raw": f"3km 內藥局/醫院 {v} 家{eff_txt}",
            "basis": (f"近者綜效強：步行 {WALK_KM:.0f}km 內權重 1.0，至車程 "
                      f"{DRIVE_KM:.0f}km 線性衰減至 {COMPETITION_FLOOR}；有效家數映射 "
                      f"{ANCHOR_LO:.0f}–{ANCHOR_HI:.0f} → 0–100"),
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
    if name == "age_gender":
        prime = g("age_prime_share")
        if prime is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        fem = g("female_share")
        tot = g("age_pop_total")
        tot_txt = f"（村里 {tot:,} 人）" if tot else ""
        return {
            "raw": (f"壯年 25–49 占 {prime * 100:.1f}%、女性占 "
                    f"{(fem or 0) * 100:.1f}%{tot_txt}"),
            "basis": (f"自費客群代理：壯年占比映射 {AGE_PRIME_LO:.0%}–{AGE_PRIME_HI:.0%}、"
                      f"女性占比映射 {FEMALE_LO:.0%}–{FEMALE_HI:.0%}，"
                      f"加權 {AGE_PRIME_WEIGHT:.0%}:{1 - AGE_PRIME_WEIGHT:.0%} → 0–100"),
        }
    if name == "day_night_gap":
        ratio = g("business_ratio")
        if ratio is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        lean = "日夜均衡" if 0.85 <= ratio <= 1.15 else (
            "就業聚集型" if ratio > 1.15 else "住宅睡城型")
        return {
            "raw": f"營業家數每千人為全國 {ratio:.2f} 倍（{lean}）",
            "basis": "比值=1 日夜最均衡得分最高；偏離以 |ln(比值)| 線性扣分",
        }
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
