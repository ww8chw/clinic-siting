def minmax_score(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """把 value 依 [lo, hi] 線性映射到 0–100，超出範圍 clamp。
    invert=True 用於負向因子（值越大分數越低，如競爭密度）。
    lo == hi 時回傳中性值 50。"""
    if hi == lo:
        return 50.0
    pct = (value - lo) / (hi - lo)
    pct = max(0.0, min(1.0, pct))
    score = pct * 100.0
    return 100.0 - score if invert else score
