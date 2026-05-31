from clinic_siting.analysis.aggregate import (
    WALK_KM,
    DRIVE_KM,
    COMPETITION_FLOOR,
    count_within,
    weighted_count_within,
    proximity_weight,
    dual_radius_counts,
    summarize_points,
)

# 龜山樂善二路 503 號
CENTER = (25.0461974, 121.3918275)

# 0.005 deg ≈ 0.55km（walk+drive 內）
P_CLOSE = {"lat": CENTER[0] + 0.005, "lon": CENTER[1]}
# 0.02 deg ≈ 2.2km（僅 drive 內）
P_MID = {"lat": CENTER[0] + 0.02, "lon": CENTER[1]}
# 0.05 deg ≈ 5.5km（兩者皆外）
P_FAR = {"lat": CENTER[0] + 0.05, "lon": CENTER[1]}


def test_radii_constants():
    assert WALK_KM == 1.0
    assert DRIVE_KM == 3.0


def test_count_within_boundary():
    pts = [P_CLOSE, P_MID, P_FAR]
    assert count_within(CENTER, pts, WALK_KM) == 1
    assert count_within(CENTER, pts, DRIVE_KM) == 2


def test_dual_radius_counts():
    pts = [P_CLOSE, P_MID, P_FAR]
    assert dual_radius_counts(CENTER, pts) == {"walk": 1, "drive": 2}


def test_proximity_weight_full_within_walk():
    # 步行半徑內（含邊界）視為等強直接競爭，權重 1.0
    assert proximity_weight(0.0) == 1.0
    assert proximity_weight(0.5) == 1.0
    assert proximity_weight(WALK_KM) == 1.0


def test_proximity_weight_decays_to_floor():
    # 車程半徑外不增加（已被半徑排除），邊界為 floor
    assert proximity_weight(DRIVE_KM) == COMPETITION_FLOOR
    assert proximity_weight(DRIVE_KM + 1) == COMPETITION_FLOOR
    # 中段線性遞減：2km → 1-(1-floor)*(2-1)/(3-1)
    expected = 1.0 - (1.0 - COMPETITION_FLOOR) * (2.0 - 1.0) / (3.0 - 1.0)
    assert abs(proximity_weight(2.0) - expected) < 1e-9
    # 越近權重越高
    assert proximity_weight(1.5) > proximity_weight(2.5)


def test_weighted_count_less_than_raw_count():
    pts = [P_CLOSE, P_MID, P_FAR]
    raw = count_within(CENTER, pts, DRIVE_KM)        # 2（CLOSE+MID）
    w = weighted_count_within(CENTER, pts, DRIVE_KM)
    # P_CLOSE 在步行內 → 1.0；P_MID 在車程帶 → <1；FAR 被排除
    assert raw == 2
    assert 1.0 < w < 2.0
    assert w < raw


def test_summarize_points_multiple_groups():
    named = {
        "clinics": [P_CLOSE, P_MID],
        "convenience": [P_CLOSE, P_CLOSE, P_FAR],
        "transit": [],
    }
    out = summarize_points(CENTER, named)
    assert out["clinics"] == {"walk": 1, "drive": 2}
    assert out["convenience"] == {"walk": 2, "drive": 2}
    assert out["transit"] == {"walk": 0, "drive": 0}
