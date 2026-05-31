from __future__ import annotations

from clinic_siting.geo.distance import haversine_km
from clinic_siting.geo.radius import points_within_radius

# 雙半徑：步行商圈 1km、車程商圈 3km
WALK_KM = 1.0
DRIVE_KM = 3.0
# 競爭距離衰減：車程半徑邊界仍保留的最低權重（越近的同業競爭越強）
COMPETITION_FLOOR = 0.2


def count_within(center, points, radius_km: float) -> int:
    """center (lat, lon) 半徑內的點位數量。"""
    return len(points_within_radius(center, points, radius_km))


def proximity_weight(distance_km: float,
                     walk_km: float = WALK_KM,
                     drive_km: float = DRIVE_KM,
                     floor: float = COMPETITION_FLOOR) -> float:
    """同業競爭的距離權重：步行半徑內 = 1.0，之後線性衰減至車程邊界的 floor。

    近處同業搶同一批走路病患，競爭最強；越遠影響越弱。"""
    if distance_km <= walk_km:
        return 1.0
    if distance_km >= drive_km:
        return floor
    span = drive_km - walk_km
    return 1.0 - (1.0 - floor) * (distance_km - walk_km) / span


def weighted_count_within(center, points, radius_km: float) -> float:
    """半徑內點位的距離加權有效家數（近者權重高），回傳浮點數。"""
    clat, clon = center
    total = 0.0
    for p in points_within_radius(center, points, radius_km):
        d = haversine_km(clat, clon, p["lat"], p["lon"])
        total += proximity_weight(d)
    return total


def dual_radius_counts(center, points) -> dict:
    """同一組點位的步行/車程雙半徑計數。"""
    return {
        "walk": count_within(center, points, WALK_KM),
        "drive": count_within(center, points, DRIVE_KM),
    }


def summarize_points(center, named_points: dict) -> dict:
    """對多組命名點位一次算雙半徑計數 → {名稱: {walk, drive}}。"""
    return {
        name: dual_radius_counts(center, points)
        for name, points in named_points.items()
    }
