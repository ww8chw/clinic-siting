from __future__ import annotations

from clinic_siting.data_sources.http import post_json
from clinic_siting.models import Place

_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
_SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
_FIELD_MASK = ("places.displayName,places.types,places.rating,"
               "places.userRatingCount,places.location,places.formattedAddress")


def parse_places(raw: dict) -> list[Place]:
    """把 Places New v1 (searchText/searchNearby 同形) 轉成 Place list。
    零結果時回應為 {}，回傳空 list。"""
    out: list[Place] = []
    for p in raw.get("places", []):
        loc = p.get("location", {})
        out.append(Place(
            name=p.get("displayName", {}).get("text", ""),
            lat=loc.get("latitude"),
            lon=loc.get("longitude"),
            source="google",
            types=p.get("types", []),
            rating=p.get("rating"),
            rating_count=p.get("userRatingCount"),
            address=p.get("formattedAddress", ""),
        ))
    return out


def _headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _FIELD_MASK,
    }


def fetch_search_text(query: str, lat: float, lon: float, radius_m: int,
                      api_key: str, max_results: int = 20) -> dict:
    body = {
        "textQuery": query,
        "languageCode": "zh-TW",
        "maxResultCount": max_results,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                     "radius": radius_m}},
    }
    return post_json(_SEARCH_TEXT_URL, json_body=body, headers=_headers(api_key))


def fetch_search_nearby(included_types: list[str], lat: float, lon: float, radius_m: int,
                        api_key: str, max_results: int = 20) -> dict:
    body = {
        "includedTypes": included_types,
        "languageCode": "zh-TW",
        "maxResultCount": max_results,
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                            "radius": radius_m}},
    }
    return post_json(_SEARCH_NEARBY_URL, json_body=body, headers=_headers(api_key))
