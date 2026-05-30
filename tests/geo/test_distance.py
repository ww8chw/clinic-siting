from clinic_siting.geo.distance import haversine_km


def test_zero_distance_same_point():
    assert haversine_km(25.0, 121.0, 25.0, 121.0) == 0.0


def test_known_distance_taipei_to_kaohsiung():
    # 台北車站 (25.0478, 121.5170) -> 高雄車站 (22.6394, 120.3025)
    d = haversine_km(25.0478, 121.5170, 22.6394, 120.3025)
    assert 290 < d < 310  # 實際約 296 km


def test_short_distance_within_one_km():
    # 約 0.5 km 的兩點
    d = haversine_km(25.0000, 121.5000, 25.0045, 121.5000)
    assert 0.45 < d < 0.55
