from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from clinic_siting.analysis.factors import ALL_FACTORS
from clinic_siting.data_sources import geocode


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


def latest_factor_bars(snapshots: list[dict]) -> list[dict]:
    """最新一筆的因子長條資料，依 ALL_FACTORS 順序。"""
    if not snapshots:
        return []
    factors = snapshots[-1].get("factors", {})
    bars = []
    for name in ALL_FACTORS:
        f = factors.get(name)
        if f is None:
            continue
        bars.append({"factor": name, "score": f["score"], "source": f["source"]})
    return bars


def build_payload(snapshots: list[dict]) -> dict:
    """組前端 history.json 主體（不含 geo）。"""
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "address": geocode.SITE_ADDRESS,
            "latlon": list(geocode.SITE_LATLON),
        },
        "trend": trend_series(snapshots),
        "radar": latest_radar(snapshots),
        "factors": latest_factor_bars(snapshots),
    }


def build_site(history_path, site_dir) -> None:
    """讀 jsonl → 寫 site_dir/data/history.json 與 geo.json。"""
    snapshots = _load_snapshots(history_path)
    data_dir = Path(site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(snapshots)
    (data_dir / "history.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    geo = snapshots[-1].get("geo", {}) if snapshots else {}
    (data_dir / "geo.json").write_text(
        json.dumps(geo, ensure_ascii=False, indent=2), encoding="utf-8")
