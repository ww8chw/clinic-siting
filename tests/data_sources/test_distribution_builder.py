import json
from site_siting.data_sources.distribution_builder import (
    make_distribution, income_median_values, population_values,
    write_distribution)


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
