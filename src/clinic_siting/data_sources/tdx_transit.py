from __future__ import annotations

import requests

from clinic_siting.data_sources.http import USER_AGENT, get_json
from clinic_siting.models import TransitStop

TDX_TOKEN_URL = ("https://tdx.transportdata.tw/auth/realms/TDXConnect/"
                 "protocol/openid-connect/token")
_BUS_STOP_URL = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/{city}"


def parse_bus_stops(raw: list) -> list[TransitStop]:
    """把 TDX Bus/Stop 回應轉成 TransitStop list。"""
    out: list[TransitStop] = []
    for s in raw:
        pos = s.get("StopPosition", {})
        name = s.get("StopName", {}).get("Zh_tw", "")
        if pos.get("PositionLat") is None or pos.get("PositionLon") is None:
            continue
        out.append(TransitStop(name=name, lat=pos["PositionLat"],
                               lon=pos["PositionLon"], kind="bus"))
    return out


def fetch_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(TDX_TOKEN_URL, headers={"User-Agent": USER_AGENT}, data={
        "grant_type": "client_credentials",
        "client_id": client_id, "client_secret": client_secret,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_bus_stops(lat: float, lon: float, radius_m: int, token: str,
                    city: str = "Taoyuan", top: int = 50) -> list:
    url = _BUS_STOP_URL.format(city=city)
    return get_json(url, params={
        "$spatialFilter": f"nearby({lat},{lon},{radius_m})",
        "$format": "JSON", "$top": top,
    }, headers={"authorization": f"Bearer {token}"})
