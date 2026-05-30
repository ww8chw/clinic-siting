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
    tdx_transit,
)
from clinic_siting.data_sources.reference import (
    parse_income_csv,
    parse_population_csv,
    district_income_summary,
)
from clinic_siting.scoring.config import load_specialty_config
from clinic_siting.scoring.engine import score_all_specialties
from clinic_siting.snapshot import append_snapshot, load_last_snapshot, fill_degraded

INCOME_DISTRICT = "桃園市龜山區"
POP_REGION = "龜山區"

_WALK_M = int(WALK_KM * 1000)
_DRIVE_M = int(DRIVE_KM * 1000)


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

    return {
        "weighted_median_income": summary["weighted_median"],
        "population": region["population"],
        "households": region["households"],
    }


def _points(objs) -> list[dict]:
    """把 Place/TransitStop 物件轉成 {lat, lon} 點位。"""
    return [{"lat": o.lat, "lon": o.lon} for o in objs if o.lat and o.lon]


def collect_live(center: tuple[float, float]) -> dict:
    """嘗試線上抓取，每來源失敗則略過該 key（交給 factors/snapshot 降級）。"""
    raw: dict = {}
    google_key = env.get_key("GOOGLE_MAPS_API_KEY")

    if google_key:
        try:
            resp = google_places.fetch_search_text(
                "診所", center[0], center[1], _DRIVE_M, google_key)
            clinics = _points(google_places.parse_places(resp))
            raw["competition_count"] = count_within(center, clinics, DRIVE_KM)
        except Exception:
            pass
        try:
            resp = google_places.fetch_search_nearby(
                ["pharmacy", "hospital"], center[0], center[1], _DRIVE_M, google_key)
            anchors = _points(google_places.parse_places(resp))
            raw["anchor_count"] = count_within(center, anchors, DRIVE_KM)
        except Exception:
            pass

    try:
        q = osm_poi.build_query("shop", "convenience", center[0], center[1], _WALK_M)
        conv = _points(osm_poi.parse_overpass(osm_poi.fetch_overpass(q)))
        raw["convenience_count"] = count_within(center, conv, WALK_KM)
    except Exception:
        pass

    try:
        q = osm_poi.build_query("amenity", "shop", center[0], center[1], _WALK_M)
        biz = _points(osm_poi.parse_overpass(osm_poi.fetch_overpass(q)))
        raw["business_count"] = count_within(center, biz, WALK_KM)
    except Exception:
        pass

    try:
        q = osm_poi.build_query("landuse", "residential", center[0], center[1], _DRIVE_M)
        # 不同 landuse value 各查一次，計算出現的類型數
        types = 0
        for value in ("residential", "commercial", "retail", "industrial"):
            qv = osm_poi.build_query("landuse", value, center[0], center[1], _DRIVE_M)
            els = osm_poi.parse_overpass(osm_poi.fetch_overpass(qv))
            if els:
                types += 1
        raw["landuse_types"] = types
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
        except Exception:
            pass

    return raw


def run_pipeline(reference_dir, history_path, config_path,
                 live: bool = False,
                 center: tuple[float, float] = geocode.SITE_LATLON) -> dict:
    """collect → build_factors → fill_degraded → score → 組 snapshot → append。"""
    raw = collect_offline(reference_dir)
    if live:
        raw.update(collect_live(center))

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
    }
    append_snapshot(history_path, snapshot)
    return snapshot
