from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_siting.analysis.percentile import Distribution
from site_siting.data_sources.moi_agegender import PRIME_AGES
from site_siting.data_sources.realprice import district_median_building_age


def make_distribution(factor: str, unit: str, source: str,
                      values, generated: str | None = None) -> Distribution:
    vals = sorted(float(v) for v in values)
    return Distribution(factor=factor, unit=unit, source=source,
                        generated=generated or date.today().isoformat(),
                        values=vals)


def income_median_values(income: dict[str, dict]) -> list[float]:
    """parse_income_csv 產出 → 各里中位所得（median>0 者）。"""
    return [float(r["median"]) for r in income.values() if r.get("median")]


def population_values(population: dict[str, dict]) -> list[float]:
    """parse_population_csv 產出 → 各區人口（>0 者）。"""
    return [float(r["population"]) for r in population.values()
            if r.get("population")]


def building_age_values(records, as_of_year: int, districts) -> list[float]:
    """各行政區成交屋齡中位 → list（有值者）。"""
    out = []
    for d in districts:
        age = district_median_building_age(records, d, as_of_year)
        if age is not None:
            out.append(float(age))
    return out


def age_share_values(rows) -> tuple[list[float], list[float]]:
    """ODRP052 列 → 各里(壯年占比, 女性占比) 兩條母體。
    以 (site_id, village) 分組跨婚姻狀況/年齡加總。"""
    agg: dict[tuple, dict] = {}
    for x in rows:
        key = (x.get("site_id"), x.get("village"))
        pop = int(x.get("population") or 0)
        a = agg.setdefault(key, {"total": 0, "female": 0, "prime": 0})
        a["total"] += pop
        if x.get("sex") == "女":
            a["female"] += pop
        if x.get("age") in PRIME_AGES:
            a["prime"] += pop
    prime, female = [], []
    for a in agg.values():
        if a["total"] > 0:
            prime.append(a["prime"] / a["total"])
            female.append(a["female"] / a["total"])
    return prime, female


def write_distribution(dist: Distribution, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "factor": dist.factor, "unit": dist.unit, "source": dist.source,
        "generated": dist.generated, "values": dist.values,
    }, ensure_ascii=False), encoding="utf-8")
