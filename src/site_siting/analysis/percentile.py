from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path

# 分布檔預設目錄（專案根 /data/reference/distributions）
# percentile.py 位於 src/site_siting/analysis/，故專案根為 parents[3]
DISTRIBUTIONS_DIR = (Path(__file__).resolve().parents[3]
                     / "data" / "reference" / "distributions")


@dataclass
class Distribution:
    factor: str          # 對映因子鍵（如 purchasing_power / age_prime）
    unit: str            # 母體單位："里" / "區"
    source: str          # 資料出處（稽核用）
    generated: str       # 產生日期 ISO
    values: list[float]  # 排序後的母體值

    @property
    def n(self) -> int:
        return len(self.values)


def percentile_score(value: float, dist: Distribution,
                     invert: bool = False) -> float:
    """value 在 dist.values 中的百分位（midrank，0–100）。
    空母體回中性 50。invert=True 用於反向因子（值越大分越低）。"""
    v = dist.values
    n = len(v)
    if n == 0:
        return 50.0
    lo = bisect_left(v, value)
    hi = bisect_right(v, value)
    rank = (lo + hi) / 2.0
    pct = max(0.0, min(100.0, rank / n * 100.0))
    return 100.0 - pct if invert else pct


def load_distribution(path) -> Distribution:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return Distribution(
        factor=d["factor"], unit=d["unit"], source=d["source"],
        generated=d["generated"],
        values=sorted(float(x) for x in d["values"]),
    )


def load_distributions(directory=DISTRIBUTIONS_DIR) -> dict[str, Distribution]:
    """讀目錄下所有 *.json → {factor: Distribution}。目錄不存在回 {}。"""
    directory = Path(directory)
    out: dict[str, Distribution] = {}
    if not directory.exists():
        return out
    for p in sorted(directory.glob("*.json")):
        dist = load_distribution(p)
        out[dist.factor] = dist
    return out
