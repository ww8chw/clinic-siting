from __future__ import annotations

import math

from clinic_siting.geo.distance import haversine_km


def tile_centers(center: tuple[float, float],
                 radius_km: float,
                 step_km: float) -> list[tuple[float, float]]:
    """產生覆蓋以 center 為圓心、radius_km 為半徑之圓的網格子查詢中心點（含中心）。

    Google Places searchNearby 單次最多回 20 筆且不分頁；把大圓切成多個小格、
    各自小半徑查詢再去重，才能完整掃出密集區的全部點位。保留落在 radius+step 內
    的格點（邊界略放寬，確保圓周附近不漏）。"""
    clat, clon = center
    n = int(math.ceil(radius_km / step_km))
    lat_per_km = 1.0 / 111.0
    lon_per_km = 1.0 / (111.0 * math.cos(math.radians(clat)))
    out: list[tuple[float, float]] = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            lat = clat + (i * step_km) * lat_per_km
            lon = clon + (j * step_km) * lon_per_km
            if haversine_km(clat, clon, lat, lon) <= radius_km + step_km:
                out.append((lat, lon))
    return out
