from __future__ import annotations

from clinic_siting.data_sources.http import get_json

_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def parse_distance(raw: dict) -> list[dict]:
    """攤平 Distance Matrix 回應成 list；每筆含 status / distance_m / duration_s / 文字。
    非 OK 的 element 其數值欄位為 None。"""
    out: list[dict] = []
    for row in raw.get("rows", []):
        for el in row.get("elements", []):
            status = el.get("status")
            if status == "OK":
                out.append({
                    "status": status,
                    "distance_m": el["distance"]["value"],
                    "duration_s": el["duration"]["value"],
                    "distance_text": el["distance"]["text"],
                    "duration_text": el["duration"]["text"],
                })
            else:
                out.append({"status": status, "distance_m": None, "duration_s": None,
                            "distance_text": None, "duration_text": None})
    return out


def fetch_distance_matrix(origin: tuple[float, float],
                          destinations: list[tuple[float, float]],
                          api_key: str, mode: str = "driving") -> dict:
    dest_str = "|".join(f"{lat},{lon}" for lat, lon in destinations)
    return get_json(_URL, params={
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": dest_str,
        "mode": mode, "language": "zh-TW", "key": api_key,
    })
