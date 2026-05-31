from __future__ import annotations

from clinic_siting.data_sources.http import post_json

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_nearest_road_query(lat: float, lon: float, radius_m: int) -> str:
    """組 Overpass QL：抓座標周邊具名道路的 highway way（含 highway/name/lanes tag）。

    用於能見度：臨街道路的 highway 等級與車道數越高，店面能見度越好。"""
    f = f'(around:{radius_m},{lat},{lon})["highway"]["name"]'
    return f"[out:json][timeout:25];way{f};out tags;"


def parse_roads(raw: dict) -> list[dict]:
    """Overpass 回應 → [{name, highway, lanes}]；無 highway tag 者略過。"""
    out: list[dict] = []
    for el in raw.get("elements", []):
        tags = el.get("tags", {})
        highway = tags.get("highway")
        if not highway:
            continue
        lanes_raw = tags.get("lanes")
        try:
            lanes = int(lanes_raw) if lanes_raw is not None else None
        except (TypeError, ValueError):
            lanes = None
        out.append({
            "name": tags.get("name", ""),
            "highway": highway,
            "lanes": lanes,
        })
    return out


def fetch_roads(query: str) -> dict:
    return post_json(_OVERPASS_URL, data={"data": query})
