from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from clinic_siting.analysis.factors import ALL_FACTORS, factor_explanation
from clinic_siting.data_sources import geocode

# 數值權重 → 等級標籤（對齊 config/specialties.yaml 的 weight_levels）
WEIGHT_LABELS = {5: "最高", 4: "高", 3: "中", 2: "低", 0: "無"}


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


def trend_series(snapshots: list[dict]) -> dict:
    """跨快照折線資料：{dates, specialties: {name: [score,...]}}。"""
    dates = [s["date"] for s in snapshots]
    names: list[str] = []
    for s in snapshots:
        for n in s.get("scores", {}):
            if n not in names:
                names.append(n)
    specialties = {
        n: [s.get("scores", {}).get(n) for s in snapshots]
        for n in names
    }
    return {"dates": dates, "specialties": specialties}


def latest_radar(snapshots: list[dict]) -> dict:
    """最新一筆的五科別雷達資料：{labels, scores}。"""
    if not snapshots:
        return {"labels": [], "scores": []}
    scores = snapshots[-1].get("scores", {})
    labels = list(scores.keys())
    return {"labels": labels, "scores": [scores[n] for n in labels]}


def latest_factor_table(snapshots: list[dict]) -> list[dict]:
    """最新一筆的因子明細：原始數據、換算依據、正規化分、來源（依 ALL_FACTORS 順序）。"""
    if not snapshots:
        return []
    snap = snapshots[-1]
    factors = snap.get("factors", {})
    raw = snap.get("raw", {})
    rows = []
    for name in ALL_FACTORS:
        f = factors.get(name)
        if f is None:
            continue
        exp = factor_explanation(name, raw)
        rows.append({
            "factor": name,
            "score": f["score"],
            "source": f["source"],
            "raw_text": exp["raw"],
            "basis_text": exp["basis"],
        })
    return rows


def specialty_breakdowns(snapshots: list[dict], config) -> dict:
    """最新一筆各科的加權拆解：每因子 權重×因子分÷總權重=貢獻，加總=總分。

    回傳 {科別: {total, rows: [{factor, weight, level, score, contribution}]}}。
    config 為 None 時回傳 {}。"""
    if not snapshots or config is None:
        return {}
    factor_score = {n: f["score"] for n, f in snapshots[-1].get("factors", {}).items()}
    out: dict[str, dict] = {}
    for name, weights in config.specialties.items():
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
        out[name] = {
            "total": round(sum(r["contribution"] for r in rows), 2),
            "rows": rows,
        }
    return out


def build_payload(snapshots: list[dict], config=None) -> dict:
    """組前端 history.json 主體（不含 geo）。"""
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "address": geocode.SITE_ADDRESS,
            "latlon": list(geocode.SITE_LATLON),
        },
        "trend": trend_series(snapshots),
        "radar": latest_radar(snapshots),
        "factors": latest_factor_table(snapshots),
        "breakdowns": specialty_breakdowns(snapshots, config),
    }


def build_site(history_path, site_dir, config=None) -> None:
    """讀 jsonl → 寫 site_dir/data/history.json 與 geo.json。"""
    snapshots = _load_snapshots(history_path)
    data_dir = Path(site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(snapshots, config)
    (data_dir / "history.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    geo = snapshots[-1].get("geo", {}) if snapshots else {}
    (data_dir / "geo.json").write_text(
        json.dumps(geo, ensure_ascii=False, indent=2), encoding="utf-8")
