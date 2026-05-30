from clinic_siting.geo.distance import haversine_km

Point = dict  # 需含 "lat", "lon" 鍵


def points_within_radius(center, points, radius_km: float):
    """回傳 center (lat, lon) 半徑 radius_km 公里內的點位 list。"""
    clat, clon = center
    return [
        p for p in points
        if haversine_km(clat, clon, p["lat"], p["lon"]) <= radius_km
    ]
