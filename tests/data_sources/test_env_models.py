from clinic_siting.models import Place, TransitStop, Clinic


def test_place_defaults():
    p = Place(name="A", lat=25.0, lon=121.0, source="google")
    assert p.rating is None
    assert p.rating_count is None
    assert p.types == []


def test_transit_stop_fields():
    s = TransitStop(name="文林路口", lat=25.04, lon=121.39, kind="bus")
    assert s.kind == "bus"


def test_clinic_specialties_list():
    c = Clinic(code="X", name="某診所", kind="西醫診所",
               address="桃園市龜山區...", specialties=["家醫科", "不分科"])
    assert "家醫科" in c.specialties
    assert c.lat is None
