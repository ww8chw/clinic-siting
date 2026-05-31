from clinic_siting.data_sources.moi_agegender import (
    aggregate_shares,
    collect_village_shares,
    build_url,
)

# 兩村里、跨性別/年齡/婚姻狀況的最小樣本
SAMPLE = [
    {"site_id": "桃園市龜山區", "village": "樂善里", "district_code": "68000070010",
     "sex": "男", "age": "未滿15歲", "marital_status": "未婚", "population": "100"},
    {"site_id": "桃園市龜山區", "village": "樂善里", "district_code": "68000070010",
     "sex": "女", "age": "未滿15歲", "marital_status": "未婚", "population": "100"},
    {"site_id": "桃園市龜山區", "village": "樂善里", "district_code": "68000070010",
     "sex": "男", "age": "30~34歲", "marital_status": "未婚", "population": "60"},
    {"site_id": "桃園市龜山區", "village": "樂善里", "district_code": "68000070010",
     "sex": "男", "age": "30~34歲", "marital_status": "有偶_不同性別", "population": "40"},
    {"site_id": "桃園市龜山區", "village": "樂善里", "district_code": "68000070010",
     "sex": "女", "age": "40~44歲", "marital_status": "未婚", "population": "100"},
    # 另一村里不應計入
    {"site_id": "桃園市龜山區", "village": "其他里", "district_code": "68000070011",
     "sex": "男", "age": "30~34歲", "marital_status": "未婚", "population": "999"},
]


def test_aggregate_shares_sums_over_marital():
    s = aggregate_shares(SAMPLE, "桃園市龜山區", "樂善里")
    # 樂善里：男100+女100(未滿15) + 男60+40(30-34) + 女100(40-44) = 400
    assert s["total"] == 400
    # 女性：100 + 100 = 200
    assert s["female_share"] == 0.5
    # 壯年(25-49)：男100(30-34) + 女100(40-44) = 200
    assert s["prime_share"] == 0.5


def test_aggregate_shares_missing_village_returns_none():
    assert aggregate_shares(SAMPLE, "桃園市龜山區", "不存在里") is None


def test_build_url():
    assert build_url("114", 3).endswith("/ODRP052/114?page=3")


def _other(code, sid):
    return [{"district_code": code, "site_id": sid, "village": "x", "sex": "男",
             "age": "30~34歲", "marital_status": "未婚", "population": "1"}]


def test_collect_village_window_scan_finds_block():
    # 模擬 10 頁，龜山樂善里在第 6 頁（hint 命中半徑內）
    pages = {p: _other("65000010001", "新北市板橋區") for p in range(1, 11)}
    pages[6] = SAMPLE
    calls = {"n": 0}

    def fake_fetch(year, page):
        calls["n"] += 1
        return {"totalPage": "10", "responseData": pages.get(page, [])}

    s = collect_village_shares("桃園市龜山區", "樂善里",
                               year="114", fetch=fake_fetch, hint_page=6)
    assert s["total"] == 400
    assert s["prime_share"] == 0.5


def test_collect_village_widens_when_not_in_first_window():
    # 樂善里在第 30 頁，初始半徑 6 找不到 → 放大命中
    pages = {p: _other("65000010001", "新北市板橋區") for p in range(1, 41)}
    pages[30] = SAMPLE

    def fake_fetch(year, page):
        return {"totalPage": "40", "responseData": pages.get(page, [])}

    s = collect_village_shares("桃園市龜山區", "樂善里",
                               year="114", fetch=fake_fetch, hint_page=10)
    assert s is not None
    assert s["total"] == 400


def test_collect_village_tolerates_bad_page():
    # 某頁 fetch 失敗不應中斷整體掃描
    pages = {1: _other("65000010001", "新北市板橋區"), 6: SAMPLE}

    def fake_fetch(year, page):
        if page == 4:
            raise ValueError("壞掉的 JSON")
        return {"totalPage": "10", "responseData": pages.get(page, [])}

    s = collect_village_shares("桃園市龜山區", "樂善里",
                               year="114", fetch=fake_fetch, hint_page=6)
    assert s["total"] == 400
