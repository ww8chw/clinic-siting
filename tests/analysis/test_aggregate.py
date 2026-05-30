from clinic_siting.analysis.aggregate import (
    WALK_KM,
    DRIVE_KM,
    count_within,
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
