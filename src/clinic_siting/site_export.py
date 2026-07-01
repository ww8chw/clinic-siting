from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from clinic_siting.analysis.factors import ALL_FACTORS, factor_explanation
from clinic_siting.data_sources import geocode

# 數值權重 → 等級標籤（對齊 config/industries.yaml 的 weight_levels）
WEIGHT_LABELS = {5: "最高", 4: "高", 3: "中", 2: "低", 0: "無"}

# 地點因子（全行業共用）＝全因子扣掉行業專屬的競爭/互補錨點
LOCATION_FACTORS = [f for f in ALL_FACTORS
                    if f not in ("competition", "complementary_anchors")]


def _load_snapshots(history_path) -> list[dict]:
    path = Path(history_path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _factor_row(name, factors, prev_factors, raw):
    f = factors.get(name)
    if f is None:
        return None
    exp = factor_explanation(name, raw)
    pf = prev_factors.get(name)
    prev_score = pf["score"] if pf else None
    delta = (f["score"] - prev_score) if prev_score is not None else None
    delta_pct = (delta / prev_score * 100.0) if (delta is not None and prev_score) else None
    return {
        "factor": name,
        "score": f["score"],
        "source": f["source"],
        "raw_text": exp["raw"],
        "basis_text": exp["basis"],
        "prev_score": prev_score,
        "delta": round(delta, 2) if delta is not None else None,
        "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
    }


def _location_factor_table(snapshots: list[dict]) -> list[dict]:
    """共用地點因子明細（11 因子）：原始數據、依據、正規化分、來源、與上一筆變化。"""
    if not snapshots:
        return []
    snap = snapshots[-1].get("location", {})
    prev = snapshots[-2].get("location", {}) if len(snapshots) >= 2 else {}
    factors = snap.get("factors", {})
    prev_factors = prev.get("factors", {})
    raw = snap.get("raw", {})
    rows = []
    for name in LOCATION_FACTORS:
        row = _factor_row(name, factors, prev_factors, raw)
        if row is not None:
            rows.append(row)
    return rows


def _industry_factor_table(snapshots: list[dict], iid: str) -> list[dict]:
    """某行業的完整 13 因子明細（地點因子 + 該行業競爭/錨點）。"""
    if not snapshots:
        return []
    snap = snapshots[-1]
    prev = snapshots[-2] if len(snapshots) >= 2 else None
    meta = snap.get("industries", {}).get(iid, {})
    factors = meta.get("factors", {})
    prev_factors = (prev.get("industries", {}).get(iid, {}).get("factors", {})
                    if prev else {})
    # raw 合併地點與該行業（供 competition_pools/anchor 說明用）
    raw = dict(snap.get("location", {}).get("raw", {}))
    raw.update(meta.get("raw", {}))
    rows = []
    for name in ALL_FACTORS:
        row = _factor_row(name, factors, prev_factors, raw)
        if row is not None:
            rows.append(row)
    return rows


def _industry_breakdown(meta: dict, config, iid: str) -> dict | None:
    """某行業的加權拆解：每因子 權重×因子分÷總權重=貢獻，加總=總分。"""
    if config is None or iid not in config.industries:
        return None
    weights = config.industries[iid].weights
    factor_score = {n: f["score"] for n, f in meta.get("factors", {}).items()}
    total_w = sum(weights.values())
    rows = []
    for factor in ALL_FACTORS:
        w = weights.get(factor, 0)
        score = factor_score.get(factor)
        contribution = (score * w / total_w) if (total_w and score is not None) else 0.0
        rows.append({
            "factor": factor,
            "weight": w,
            "level": WEIGHT_LABELS.get(w, str(w)),
            "score": score,
            "contribution": round(contribution, 2),
        })
    return {
        "total": round(sum(r["contribution"] for r in rows), 2),
        "rows": rows,
    }


def build_payload(snapshots: list[dict], config=None) -> dict:
    """組前端 history.json 主體：地點因子共用區塊 + 依 group/industry 分組。"""
    latest = snapshots[-1] if snapshots else {}
    dates = [s["date"] for s in snapshots]
    industries_meta = latest.get("industries", {})

    groups: dict[str, dict] = {}
    for iid, meta in industries_meta.items():
        g = meta["group"]
        trend = [s.get("industries", {}).get(iid, {}).get("score") for s in snapshots]
        entry = {
            "label": meta["label"],
            "score": meta["score"],
            "trend": trend,
            "factors": _industry_factor_table(snapshots, iid),
            "breakdown": _industry_breakdown(meta, config, iid),
            "geo": meta.get("geo", {}),
        }
        groups.setdefault(g, {"industries": {}})["industries"][iid] = entry

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "address": geocode.SITE_ADDRESS,
            "latlon": list(geocode.SITE_LATLON),
        },
        "dates": dates,
        "location_factors": _location_factor_table(snapshots),
        "groups": groups,
    }


def build_site(history_path, site_dir, config=None) -> None:
    """讀 jsonl → 寫 site_dir/data/history.json 與 geo.json（geo 依 industry id）。"""
    snapshots = _load_snapshots(history_path)
    data_dir = Path(site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(snapshots, config)
    (data_dir / "history.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    geo = {iid: d.get("geo", {})
           for iid, d in (snapshots[-1].get("industries", {})
                          if snapshots else {}).items()}
    (data_dir / "geo.json").write_text(
        json.dumps(geo, ensure_ascii=False, indent=2), encoding="utf-8")
