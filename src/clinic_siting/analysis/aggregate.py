from __future__ import annotations

from clinic_siting.geo.radius import points_within_radius

# 雙半徑：步行商圈 1km、車程商圈 3km
WALK_KM = 1.0
DRIVE_KM = 3.0


def count_within(center, points, radius_km: float) -> int:
    """center (lat, lon) 半徑內的點位數量。"""
    return len(points_within_radius(center, points, radius_km))


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
