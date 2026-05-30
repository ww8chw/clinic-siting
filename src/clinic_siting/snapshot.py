from __future__ import annotations

import json
from pathlib import Path

from clinic_siting.analysis.factors import FactorResult

# 可沿用為降級值的來源（曾經是真實資料）
_REUSABLE = {"real", "degraded"}


def append_snapshot(path, snapshot: dict) -> None:
    """JSONL 追加一筆快照（含 date / scores / factors / raw）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def load_last_snapshot(path) -> dict | None:
    """讀取最後一筆快照；檔案不存在或為空回傳 None。"""
    path = Path(path)
    if not path.exists():
        return None
    last = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            last = line
    return json.loads(last) if last else None


def fill_degraded(factors: dict[str, FactorResult],
                  last: dict | None) -> dict[str, FactorResult]:
    """source==missing 且上次快照該因子有真值 → 沿用並標 degraded。"""
    if not last:
        return factors
    last_factors = last.get("factors", {})
    for name, result in factors.items():
        if result.source != "missing":
            continue
        prev = last_factors.get(name)
        if prev and prev.get("source") in _REUSABLE:
            factors[name] = FactorResult(prev["score"], "degraded")
    return factors
