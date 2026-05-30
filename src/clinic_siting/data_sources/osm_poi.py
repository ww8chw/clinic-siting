from __future__ import annotations

from clinic_siting.data_sources.http import post_json
from clinic_siting.models import Place

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query(key: str, value: str, lat: float, lon: float, radius_m: int) -> str:
    """組 Overpass QL：抓指定 tag 的 node，含 way/relation 的中心點。"""
    f = f'["{key}"="{value}"](around:{radius_m},{lat},{lon})'
    return (f"[out:json][timeout:25];"
            f"(node{f};way{f};relation{f};);out center;")


def parse_overpass(raw: dict) -> list[Place]:
    """把 Overpass 回應轉成 Place list；way/relation 取 center 座標。"""
    out: list[Place] = []
    for el in raw.get("elements", []):
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        out.append(Place(
            name=tags.get("name", ""),
            lat=lat, lon=lon, source="osm",
            types=[f"{k}={v}" for k, v in tags.items()
                   if k in ("shop", "amenity", "leisure", "healthcare")],
        ))
    return out


def fetch_overpass(query: str) -> dict:
    return post_json(_OVERPASS_URL, data={"data": query})
