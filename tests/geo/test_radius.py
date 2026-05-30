from clinic_siting.geo.radius import points_within_radius


def test_filters_points_inside_radius():
    center = (25.0000, 121.5000)
    points = [
        {"id": "near", "lat": 25.0045, "lon": 121.5000},   # ~0.5 km
        {"id": "far", "lat": 25.1000, "lon": 121.5000},    # ~11 km
    ]
    result = points_within_radius(center, points, radius_km=1.0)
    ids = [p["id"] for p in result]
    assert ids == ["near"]


def test_empty_when_none_inside():
    center = (25.0, 121.5)
    points = [{"id": "x", "lat": 26.0, "lon": 121.5}]
    assert points_within_radius(center, points, radius_km=1.0) == []


def test_boundary_point_included():
    center = (25.0, 121.5)
    # 放一個約 0.9 km 的點，半徑 1 km 應納入
    points = [{"id": "edge", "lat": 25.0081, "lon": 121.5000}]
    result = points_within_radius(center, points, radius_km=1.0)
    assert [p["id"] for p in result] == ["edge"]
