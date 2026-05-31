from clinic_siting.geo.grid import tile_centers
from clinic_siting.geo.distance import haversine_km

CENTER = (25.0461974, 121.3918275)


def test_tile_centers_includes_center_and_covers_radius():
    tiles = tile_centers(CENTER, radius_km=3.0, step_km=1.2)
    # 含中心點
    assert any(abs(la - CENTER[0]) < 1e-9 and abs(lo - CENTER[1]) < 1e-9
               for la, lo in tiles)
    # 多於 1 格（突破單次查詢上限的重點）
    assert len(tiles) > 1
    # 所有格點都落在 radius+step 內
    for la, lo in tiles:
        assert haversine_km(CENTER[0], CENTER[1], la, lo) <= 3.0 + 1.2 + 1e-6


def test_tile_centers_denser_step_yields_more_tiles():
    coarse = tile_centers(CENTER, 3.0, 1.5)
    fine = tile_centers(CENTER, 3.0, 0.8)
    assert len(fine) > len(coarse)
