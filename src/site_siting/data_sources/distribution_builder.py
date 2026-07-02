from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_siting.analysis.percentile import Distribution
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


def write_distribution(dist: Distribution, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "factor": dist.factor, "unit": dist.unit, "source": dist.source,
        "generated": dist.generated, "values": dist.values,
    }, ensure_ascii=False), encoding="utf-8")
