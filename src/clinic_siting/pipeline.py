from __future__ import annotations

from datetime import date
from pathlib import Path

from clinic_siting.analysis.aggregate import (
    WALK_KM, DRIVE_KM, count_within, weighted_count_within)
from clinic_siting.analysis.competition import classify_place
from clinic_siting.geo.distance import haversine_km
from clinic_siting.geo.grid import tile_centers
from clinic_siting.analysis.factors import build_factors, factor_scores
from clinic_siting.data_sources import (
    env,
    fia_business,
    geocode,
    google_places,
    moi_agegender,
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
SITE_SITE_ID = "桃園市龜山區"     # ODRP052 site_id 欄位值
SITE_VILLAGE = "樂善里"          # 候選點所在村里（樂善二路503號）
NATIONAL_POP = 23_400_000        # 全國人口（晝夜比值正規化基準）

_WALK_M = int(WALK_KM * 1000)
_DRIVE_M = int(DRIVE_KM * 1000)
_VISIBILITY_M = 150          # 能見度只看店面臨街範圍

# 競爭掃描：分區網格突破 Google searchNearby 單次 20 筆上限
# 廣納各型別後以 classify_place 分流（台灣診所多為 medical_clinic，僅查 doctor 會漏）
_COMP_TYPES = ["doctor", "medical_clinic", "dentist", "beauty_salon", "spa",
               "skin_care_clinic", "hospital", "nail_salon", "hair_care",
               "wellness_center"]
_COMP_STEP_KM = 1.2          # 網格間距
_COMP_SUB_M = 900            # 每格子查詢半徑（略大於半格對角，確保不漏）


def _scan_competitors(center: tuple[float, float], api_key: str):
    """分區網格掃描 3km 內競爭點位，依座標去重後分流成 (western, aesthetic)。

    western＝西醫一般診所（家醫/功能/減重/精神競爭池）；
    aesthetic＝醫美/美容（醫美科競爭池）。牙醫/中醫/醫院/其他不計入競爭。"""
    seen: dict = {}
    for la, lo in tile_centers(center, DRIVE_KM, _COMP_STEP_KM):
        try:
            resp = google_places.fetch_search_nearby(
                _COMP_TYPES, la, lo, _COMP_SUB_M, api_key)
        except Exception:
            continue
        for p in google_places.parse_places(resp):
            if not (p.lat and p.lon):
                continue
            d = haversine_km(center[0], center[1], p.lat, p.lon)
            if d > DRIVE_KM:
                continue
            seen[(round(p.lat, 5), round(p.lon, 5))] = (
                p, round(d, 2), classify_place(p.name, p.types))

    western: list[dict] = []
    aesthetic: list[dict] = []
    for p, d, cat in seen.values():
        pt = {"lat": p.lat, "lon": p.lon, "name": p.name, "dist_km": d}
        if getattr(p, "address", ""):
            pt["address"] = p.address
        if getattr(p, "rating", None) is not None:
            pt["rating"] = p.rating
            pt["rating_count"] = getattr(p, "rating_count", None)
        if cat == "western":
            western.append(pt)
        elif cat == "aesthetic":
            aesthetic.append(pt)
    return western, aesthetic


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
            # 分區網格掃描＋分類，分別算西醫一般診所與醫美/美容競爭
            western, aesthetic = _scan_competitors(center, google_key)
            raw["competition_count"] = count_within(center, western, DRIVE_KM)
            raw["competition_weighted"] = round(
                weighted_count_within(center, western, DRIVE_KM), 2)
            raw["competition_aesthetic_count"] = count_within(
                center, aesthetic, DRIVE_KM)
            raw["competition_aesthetic_weighted"] = round(
                weighted_count_within(center, aesthetic, DRIVE_KM), 2)
            geo["clinics"] = western
            geo["aesthetic"] = aesthetic
        except Exception:
            pass
        try:
            resp = google_places.fetch_search_nearby(
                ["pharmacy", "hospital"], center[0], center[1], _DRIVE_M, google_key)
            anchors = _points(google_places.parse_places(resp))
            for a in anchors:
                a["dist_km"] = round(
                    haversine_km(center[0], center[1], a["lat"], a["lon"]), 2)
            raw["anchor_count"] = count_within(center, anchors, DRIVE_KM)
            raw["anchor_weighted"] = round(
                weighted_count_within(center, anchors, DRIVE_KM), 2)
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

    # 學校鄰近：步行 1km 內學校（日間人流/年輕家庭客群代理）
    try:
        q = osm_poi.build_query("amenity", "school", center[0], center[1], _WALK_M)
        schools = _points(osm_poi.parse_overpass(osm_poi.fetch_overpass(q)))
        for s in schools:
            s["dist_km"] = round(
                haversine_km(center[0], center[1], s["lat"], s["lon"]), 2)
        raw["school_count"] = count_within(center, schools, WALK_KM)
        geo["schools"] = schools
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

    # 年齡/性別：內政部 ODRP052 村里壯年(25–49)占比與女性占比
    try:
        shares = moi_agegender.collect_village_shares(SITE_SITE_ID, SITE_VILLAGE)
        if shares is not None:
            raw["age_prime_share"] = round(shares["prime_share"], 4)
            raw["female_share"] = round(shares["female_share"], 4)
            raw["age_pop_total"] = shares["total"]
    except Exception:
        pass

    # 晝夜落差：財政部稅籍登記家數（人口在 collect_offline，比值於 run_pipeline 算）
    try:
        d_count, total = fia_business.fetch_counts(POP_REGION)
        raw["fia_business_count"] = d_count
        raw["fia_business_total"] = total
    except Exception:
        pass

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
        # 晝夜比值：營業家數（line）+ 區人口（collect_offline）合併後才能算
        if "fia_business_count" in raw and "fia_business_total" in raw:
            ratio = fia_business.business_ratio(
                raw["fia_business_count"], raw["fia_business_total"],
                raw.get("population", 0), NATIONAL_POP)
            if ratio is not None:
                raw["business_ratio"] = round(ratio, 3)

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
