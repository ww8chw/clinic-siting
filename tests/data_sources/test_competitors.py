from clinic_siting.data_sources.competitors import (
    scan_pool, scan_anchors)


def _fake_google(types, keywords):
    # 回傳固定點位（帶 name/types），忽略 types/keywords
    return [
        {"lat": 25.0, "lon": 121.0, "name": "康健診所", "types": ["medical_clinic"]},
        {"lat": 25.001, "lon": 121.0, "name": "美麗醫美診所", "types": ["skin_care_clinic"]},
        {"lat": 25.002, "lon": 121.0, "name": "王小明牙醫", "types": ["dentist"]},
    ]


def _fake_osm(tags):
    return [{"lat": 25.0, "lon": 121.0, "name": "阿宗麵線", "types": []}]


CENTER = (25.0, 121.0)


def test_google_pool_classify_western():
    pool = {"source": "google_places", "pool": "western",
            "types": ["medical_clinic"], "classify": "western"}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    names = {p["name"] for p in pts}
    assert "康健診所" in names           # western
    assert "美麗醫美診所" not in names   # aesthetic 被濾掉
    assert "王小明牙醫" not in names     # dental 被濾掉


def test_google_pool_classify_aesthetic():
    pool = {"source": "google_places", "pool": "aesthetic",
            "types": ["skin_care_clinic"], "classify": "aesthetic"}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert {p["name"] for p in pts} == {"美麗醫美診所"}


def test_osm_pool_no_classify_keeps_all():
    pool = {"source": "osm", "tags": {"amenity": "restaurant"}}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert {p["name"] for p in pts} == {"阿宗麵線"}


def test_points_have_distance():
    pool = {"source": "osm", "tags": {"amenity": "restaurant"}}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert "dist_km" in pts[0]


def test_scan_anchors_osm():
    spec = {"source": "osm", "tags": {"shop": "convenience"}}
    pts = scan_anchors(CENTER, spec, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert pts and "dist_km" in pts[0]
