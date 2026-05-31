from __future__ import annotations

from datetime import date
from pathlib import Path

from clinic_siting.analysis.aggregate import WALK_KM, DRIVE_KM, count_within
from clinic_siting.analysis.factors import build_factors, factor_scores
from clinic_siting.data_sources import (
    env,
    geocode,
    google_places,
    osm_poi,
    osm_road,
    realprice,
    tdx_transit,
)
from clinic_siting.data_sources.reference import (
    parse_income_csv,
    parse_population_csv,
    district_income_summary,
    village_summary,
)
from clinic_siting.scoring.config import load_specialty_config
from clinic_siting.scoring.engine import score_all_specialties
from clinic_siting.snapshot import append_snapshot, load_last_snapshot, fill_degraded

INCOME_DISTRICT = "桃園市龜山區"
POP_REGION = "龜山區"
SITE_VILLAGE = "樂善里"          # 候選點所在村里（樂善二路503號）

_WALK_M = int(WALK_KM * 1000)
_DRIVE_M = int(DRIVE_KM * 1000)
_VISIBILITY_M = 150          # 能見度只看店面臨街範圍


def collect_offline(reference_dir,
                    income_district: str = INCOME_DISTRICT,
                    pop_region: str = POP_REGION) -> dict:
    """只用本地參考檔產生決定性 raw（離線、可測）。"""
    reference_dir = Path(reference_dir)
    income_file = next(reference_dir.glob("income*.csv"))
    pop_file = next(reference_dir.glob("population*.csv"))

    income = parse_income_csv(income_file.read_text(encoding="utf-8-sig"))
    summary = district_income_summary(income, income_district)

    population = parse_population_csv(pop_file.read_text(encoding="utf-8-sig"))
    region = population.get(pop_region, {"population": 0, "households": 0})

    village = village_summary(income, income_district, SITE_VILLAGE,
                              region["population"])

    return {
        "weighted_median_income": summary["weighted_median"],
        "population": region["population"],
        "households": region["households"],
        "village_households": village["households"],
        "village_population_est": village["population_est"],
    }


def _points(objs) -> list[dict]:
    """把 Place/TransitStop 物件轉成點位 dict（含 name；Place 另帶 address/rating）。"""
    out = []
    for o in objs:
        if not (o.lat and o.lon):
            continue
        p = {"lat": o.lat, "lon": o.lon, "name": getattr(o, "name", "")}
        if getattr(o, "address", ""):
            p["address"] = o.address
        if getattr(o, "rating", None) is not None:
            p["rating"] = o.rating
            p["rating_count"] = getattr(o, "rating_count", None)
        out.append(p)
    return out


def collect_live(center: tuple[float, float]) -> tuple[dict, dict]:
    """嘗試線上抓取；回傳 (raw 計數, geo 點位)。
    每來源失敗則略過該 key（交給 factors/snapshot 降級）。"""
    raw: dict = {}
    geo: dict = {}
    google_key = env.get_key("GOOGLE_MAPS_API_KEY")

    if google_key:
        try:
            # nearby + locationRestriction → 嚴格限制在半徑內，計數較準
            resp = google_places.fetch_search_nearby(
                ["doctor"], center[0], center[1], _DRIVE_M, google_key)
            clinics = _points(google_places.parse_places(resp))
            raw["competition_count"] = count_within(center, clinics, DRIVE_KM)
            geo["clinics"] = clinics
        except Exception:
            pass
        try:
            resp = google_places.fetch_search_nearby(
                ["pharmacy", "hospital"], center[0], center[1], _DRIVE_M, google_key)
            anchors = _points(google_places.parse_places(resp))
            raw["anchor_count"] = count_within(center, anchors, DRIVE_KM)
            geo["anchors"] = anchors
        except Exception:
            pass

    try:
        q = osm_poi.build_query("shop", "convenience", center[0], center[1], _WALK_M)
        conv = _points(osm_poi.parse_overpass(osm_poi.fetch_overpass(q)))
        raw["convenience_count"] = count_within(center, conv, WALK_KM)
        geo["convenience"] = conv
    except Exception:
        pass

    try:
        # 餐飲為商業活動代理（amenity=restaurant 為有效 OSM tag）
        q = osm_poi.build_query("amenity", "restaurant", center[0], center[1], _WALK_M)
        biz = _points(osm_poi.parse_overpass(osm_poi.fetch_overpass(q)))
        raw["business_count"] = count_within(center, biz, WALK_KM)
    except Exception:
        pass

    # 不同 landuse value 各自獨立查詢，單一失敗不影響其餘類型計數
    types = 0
    got_landuse = False
    for value in ("residential", "commercial", "retail", "industrial"):
        try:
            qv = osm_poi.build_query("landuse", value, center[0], center[1], _DRIVE_M)
            els = osm_poi.parse_overpass(osm_poi.fetch_overpass(qv))
            got_landuse = True
            if els:
                types += 1
        except Exception:
            pass
    if got_landuse:
        raw["landuse_types"] = types

    # 能見度：周邊具名道路的 highway 等級（臨街顯眼度代理）
    try:
        rq = osm_road.build_nearest_road_query(center[0], center[1], _VISIBILITY_M)
        roads = osm_road.parse_roads(osm_road.fetch_roads(rq))
        if roads:
            raw["roads"] = roads
    except Exception:
        pass

    # 重劃/屋齡：實價登錄區級成交屋齡中位（逐季回退至可下載者）
    today = date.today()
    for season in realprice.recent_seasons(today.year, today.month, n=4):
        try:
            csv_text = realprice.fetch_lvr_main_csv(season)
            recs = realprice.parse_lvr_main_csv(csv_text)
            age = realprice.district_median_building_age(recs, POP_REGION, today.year)
            if age is not None:
                raw["building_age_median"] = age
                break
        except Exception:
            continue

    tdx_id = env.get_key("TDX_CLIENT_ID")
    tdx_secret = env.get_key("TDX_CLIENT_SECRET")
    if tdx_id and tdx_secret:
        try:
            token = tdx_transit.fetch_token(tdx_id, tdx_secret)
            stops_raw = tdx_transit.fetch_bus_stops(center[0], center[1], _WALK_M, token)
            stops = _points(tdx_transit.parse_bus_stops(stops_raw))
            raw["transit_count"] = count_within(center, stops, WALK_KM)
            geo["transit"] = stops
        except Exception:
            pass

    return raw, geo


def run_pipeline(reference_dir, history_path, config_path,
                 live: bool = False,
                 center: tuple[float, float] = geocode.SITE_LATLON,
                 site_dir=None) -> dict:
    """collect → build_factors → fill_degraded → score → 組 snapshot → append。
    給 site_dir 時，append 後重建靜態站資料。"""
    raw = collect_offline(reference_dir)
    geo: dict = {}
    if live:
        live_raw, geo = collect_live(center)
        raw.update(live_raw)

    factors = build_factors(raw)
    last = load_last_snapshot(history_path)
    factors = fill_degraded(factors, last)

    config = load_specialty_config(config_path)
    results = score_all_specialties(factor_scores(factors), config)

    snapshot = {
        "date": date.today().isoformat(),
        "scores": {name: s.score for name, s in results.items()},
        "factors": {name: {"score": r.score, "source": r.source}
                    for name, r in factors.items()},
        "raw": raw,
        "geo": geo,
    }
    append_snapshot(history_path, snapshot)

    if site_dir is not None:
        from clinic_siting.site_export import build_site
        build_site(history_path, site_dir, config)

    return snapshot
