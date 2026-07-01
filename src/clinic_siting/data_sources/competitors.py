from __future__ import annotations

from clinic_siting.analysis.aggregate import DRIVE_KM
from clinic_siting.analysis.competition import classify_place
from clinic_siting.geo.distance import haversine_km
from clinic_siting.geo.grid import tile_centers
from clinic_siting.data_sources import env, google_places, osm_poi

_COMP_STEP_KM = 1.2
_COMP_SUB_M = 900


def _default_google_fetch(center, types, keywords):
    """網格掃描 3km 內 google places；回傳點位 dict 清單（含 name/types）。"""
    key = env.get_key("GOOGLE_MAPS_API_KEY")
    if not key:
        return []
    seen: dict = {}
    for la, lo in tile_centers(center, DRIVE_KM, _COMP_STEP_KM):
        try:
            resp = google_places.fetch_search_nearby(
                types, la, lo, _COMP_SUB_M, key)
        except Exception:
            continue
        for p in google_places.parse_places(resp):
            if p.lat and p.lon:
                seen[(round(p.lat, 5), round(p.lon, 5))] = {
                    "lat": p.lat, "lon": p.lon, "name": p.name,
                    "types": list(p.types or []),
                    "address": getattr(p, "address", ""),
                    "rating": getattr(p, "rating", None),
                    "rating_count": getattr(p, "rating_count", None),
                }
    return list(seen.values())


def _default_osm_fetch(center, tags):
    """單一 tag 查 Overpass；回傳點位 dict 清單。"""
    (k, v), = tags.items()
    q = osm_poi.build_query(k, v, center[0], center[1], int(DRIVE_KM * 1000))
    out = []
    for o in osm_poi.parse_overpass(osm_poi.fetch_overpass(q)):
        if o.lat and o.lon:
            out.append({"lat": o.lat, "lon": o.lon,
                        "name": getattr(o, "name", ""), "types": []})
    return out


def _annotate(center, pts):
    for p in pts:
        p["dist_km"] = round(
            haversine_km(center[0], center[1], p["lat"], p["lon"]), 2)
    return [p for p in pts if p["dist_km"] <= DRIVE_KM]


def scan_pool(center, pool, google_fetch=None, osm_fetch=None):
    """掃一個競爭池 → 已標距離、（若有 classify）已過濾的點位清單。"""
    source = pool["source"]
    if source == "google_places":
        raw = (google_fetch or (lambda t, k: _default_google_fetch(center, t, k)))(
            pool.get("types", []), pool.get("keywords", []))
    elif source == "osm":
        raw = (osm_fetch or (lambda tg: _default_osm_fetch(center, tg)))(
            pool.get("tags", {}))
    else:
        raise ValueError(f"未知競爭來源: {source}")

    classify = pool.get("classify")
    if classify:
        raw = [p for p in raw
               if classify_place(p.get("name", ""), p.get("types")) == classify]
    return _annotate(center, raw)


def scan_anchors(center, spec, google_fetch=None, osm_fetch=None):
    """掃互補錨點 → 已標距離的點位清單。"""
    if not spec:
        return []
    source = spec["source"]
    if source == "google_places":
        raw = (google_fetch or (lambda t, k: _default_google_fetch(center, t, k)))(
            spec.get("types", []), spec.get("keywords", []))
    elif source == "osm":
        raw = (osm_fetch or (lambda tg: _default_osm_fetch(center, tg)))(
            spec.get("tags", {}))
    else:
        raise ValueError(f"未知錨點來源: {source}")
    return _annotate(center, raw)
