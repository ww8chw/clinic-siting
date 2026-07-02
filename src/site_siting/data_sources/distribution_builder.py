from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_siting.analysis.percentile import Distribution


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


def write_distribution(dist: Distribution, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "factor": dist.factor, "unit": dist.unit, "source": dist.source,
        "generated": dist.generated, "values": dist.values,
    }, ensure_ascii=False), encoding="utf-8")
