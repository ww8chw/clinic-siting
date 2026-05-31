from clinic_siting.data_sources.realprice import (
    roc_to_year,
    parse_lvr_main_csv,
    district_median_building_age,
    recent_seasons,
)

# 模擬實價登錄主檔：第1列中文欄名、第2列英文欄名、第3列起資料
SAMPLE = (
    "鄉鎮市區,土地位置建物門牌,交易年月日,建築完成年月,建物型態,編號\n"
    "district,address,txn,completion,type,id\n"
    "龜山區,樂善二路503號,1130305,1080115,住宅大樓,RPABC\n"
    "龜山區,文化一路100號,1130210,0950601,公寓,RPDEF\n"
    "龜山區,某路2號,1130101,,透天厝,RPGHI\n"     # 缺建築完成年月 → 略過
    "桃園區,中正路1號,1130105,1000101,華廈,RPJKL\n"  # 非龜山 → 不計
)


def test_roc_to_year_converts():
    assert roc_to_year("1130305") == 2024     # 民國113 → 2024
    assert roc_to_year("0950601") == 2006     # 民國95 → 2006
    assert roc_to_year("") is None
    assert roc_to_year(None) is None


def test_parse_lvr_main_csv_skips_english_header():
    recs = parse_lvr_main_csv(SAMPLE)
    # 4 筆資料列（英文表頭不算）
    assert len(recs) == 4
    r0 = recs[0]
    assert r0["district"] == "龜山區"
    assert r0["address"] == "樂善二路503號"
    assert r0["completion_date"] == "1080115"


def test_district_median_building_age():
    recs = parse_lvr_main_csv(SAMPLE)
    # 龜山區有完成年月者：1080115→2019(age7)、0950601→2006(age20)
    age = district_median_building_age(recs, "龜山區", as_of_year=2026)
    assert age == 13.5   # median(7, 20)


def test_district_median_building_age_none_when_empty():
    recs = parse_lvr_main_csv(SAMPLE)
    assert district_median_building_age(recs, "不存在區", as_of_year=2026) is None


def test_recent_seasons_descending_roc():
    seasons = recent_seasons(year=2026, month=5, n=3)
    # 2026 = 民國115；5月落在 Q2，最近已完成季為 115S1
    assert seasons[0] == "115S1"
    assert len(seasons) == 3
    # 嚴格遞減回推
    assert seasons == ["115S1", "114S4", "114S3"]
