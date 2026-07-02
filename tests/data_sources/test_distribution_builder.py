import json
from site_siting.data_sources.distribution_builder import (
    make_distribution, income_median_values, population_values,
    write_distribution, building_age_values, age_share_values)


def test_income_median_values_extracts_medians():
    income = {
        "甲里": {"district": "桃園市A區", "households": 100, "mean": 700, "median": 480},
        "乙里": {"district": "桃園市A區", "households": 200, "mean": 900, "median": 696},
        "丙里": {"district": "桃園市B區", "households": 50, "mean": 600, "median": 0},
    }
    vals = income_median_values(income)
    assert sorted(vals) == [480.0, 696.0]   # median==0 視為無資料略過


def test_population_values_extracts_population():
    pop = {
        "龜山區": {"population": 189052, "households": 87815},
        "桃園區": {"population": 478664, "households": 210351},
        "空區": {"population": 0, "households": 0},
    }
    assert sorted(population_values(pop)) == [189052.0, 478664.0]


def test_make_distribution_sorts_and_counts():
    d = make_distribution("purchasing_power", "里", "財政部",
                          [40, 10, 30], generated="2026-07-02")
    assert d.values == [10.0, 30.0, 40.0]
    assert d.n == 3
    assert d.unit == "里"


def test_write_distribution_roundtrip(tmp_path):
    d = make_distribution("population_density", "區", "內政部",
                          [3, 1, 2], generated="2026-07-02")
    p = tmp_path / "population_density.json"
    write_distribution(d, p)
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["factor"] == "population_density"
    assert loaded["source"] == "內政部"
    assert loaded["values"] == [1.0, 2.0, 3.0]
    assert loaded["generated"] == "2026-07-02"


def test_building_age_values_per_district_median():
    records = [
        {"district": "龜山區", "completion_date": "0900101"},  # 屋齡舊
        {"district": "龜山區", "completion_date": "1100101"},
        {"district": "桃園區", "completion_date": "1120101"},  # 屋齡新
        {"district": "無日期區", "completion_date": ""},        # 略過
    ]
    vals = building_age_values(records, as_of_year=2026,
                               districts=["龜山區", "桃園區", "無日期區"])
    # 龜山區 median(屋齡[25,5])=15、桃園區=3；無日期區無值不計
    assert sorted(vals) == [3.0, 15.0]


def test_age_share_values_prime_and_female_per_village():
    # ODRP052 列：{site_id, village, sex, age, population}
    rows = [
        {"site_id": "A", "village": "甲", "sex": "男", "age": "30~34歲", "population": "40"},
        {"site_id": "A", "village": "甲", "sex": "女", "age": "30~34歲", "population": "60"},
        {"site_id": "A", "village": "乙", "sex": "女", "age": "10~14歲", "population": "50"},
        {"site_id": "A", "village": "乙", "sex": "男", "age": "10~14歲", "population": "50"},
    ]
    prime, female = age_share_values(rows)
    # 甲里：壯年100/100=1.0、女60/100=0.6；乙里：壯年0/100=0、女50/100=0.5
    assert sorted(prime) == [0.0, 1.0]
    assert sorted(female) == [0.5, 0.6]
