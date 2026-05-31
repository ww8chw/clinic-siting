from pathlib import Path

from clinic_siting.data_sources.reference import (
    parse_income_csv,
    parse_population_csv,
    district_income_summary,
    village_summary,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures"
INCOME = (FIX / "income_guishan_sample.csv").read_text(encoding="utf-8-sig")
POP = (FIX / "population_taoyuan_sample.csv").read_text(encoding="utf-8-sig")


def test_parse_income_returns_village_map():
    inc = parse_income_csv(INCOME)
    assert "樂善里" in inc
    row = inc["樂善里"]
    assert row["households"] == 5166
    assert row["median"] == 696
    assert row["mean"] > 0
    assert row["district"] == "桃園市龜山區"


def test_parse_population_sums_both_sexes():
    pop = parse_population_csv(POP)
    assert "龜山區" in pop
    g = pop["龜山區"]
    # 92612 + 96440
    assert g["population"] == 189052
    # 戶數只在性別=1 列
    assert g["households"] == 87815


def test_parse_population_strips_district_suffix_and_keeps_multiple():
    pop = parse_population_csv(POP)
    assert "桃園區" in pop
    assert pop["桃園區"]["population"] == 229554 + 249110


def test_district_income_summary_population_weighted():
    inc = parse_income_csv(INCOME)
    summ = district_income_summary(inc, "桃園市龜山區")
    # 5 個村里戶數加總
    assert summ["total_households"] == 2346 + 1814 + 1323 + 1470 + 5166
    # 戶數加權中位所得介於最小與最大村里中位之間
    assert 406 <= summ["weighted_median"] <= 696
    assert summ["village_count"] == 5


def test_village_summary_households_and_population_estimate():
    inc = parse_income_csv(INCOME)
    s = village_summary(inc, "桃園市龜山區", "樂善里",
                        district_population=189052)
    assert s["households"] == 5166
    total_hh = 2346 + 1814 + 1323 + 1470 + 5166
    # 人口估 = 區人口 × 里戶數 / 區總戶數
    expected = round(189052 * 5166 / total_hh)
    assert s["population_est"] == expected
    assert s["estimated"] is True


def test_village_summary_missing_village():
    inc = parse_income_csv(INCOME)
    s = village_summary(inc, "桃園市龜山區", "不存在里",
                        district_population=189052)
    assert s["households"] is None
    assert s["population_est"] is None
