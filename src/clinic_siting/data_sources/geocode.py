from __future__ import annotations

from clinic_siting.data_sources.http import get_json

SITE_ADDRESS = "桃園市龜山區樂善二路503號"
SITE_LATLON = (25.0461974, 121.3918275)  # 由 Google Geocoding 取得、寫死

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def parse_geocode(raw: dict) -> tuple[float, float, str]:
    """從 Google Geocoding 回應取 (lat, lon, formatted_address)。"""
    if raw.get("status") != "OK" or not raw.get("results"):
        raise ValueError(f"geocode 失敗: status={raw.get('status')}")
    r = raw["results"][0]
    loc = r["geometry"]["location"]
    return loc["lat"], loc["lng"], r["formatted_address"]


def fetch_geocode(address: str, api_key: str) -> dict:
    return get_json(_GEOCODE_URL, params={
        "address": address, "language": "zh-TW", "key": api_key,
    })
