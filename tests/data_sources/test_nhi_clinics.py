from pathlib import Path

from clinic_siting.data_sources.nhi_clinics import parse_nhi_csv
from clinic_siting.models import Clinic

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "nhi_clinics_guishan_sample.csv"


def test_parse_filters_by_district_keyword():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    assert len(clinics) >= 1
    assert all(isinstance(c, Clinic) for c in clinics)
    assert all("龜山" in c.address for c in clinics)


def test_specialties_split_into_list():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    # 至少一家有解析出多科別（fixture 內有「不分科,家醫科」）
    assert any(len(c.specialties) >= 2 for c in clinics)
    # 科別字串不應殘留逗號
    assert all("," not in s for c in clinics for s in c.specialties)


def test_filter_excludes_non_matching_district():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="不存在的地名XYZ")
    assert clinics == []


def test_kind_preserved():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    assert any("診所" in c.kind for c in clinics)
