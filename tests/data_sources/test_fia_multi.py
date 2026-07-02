from site_siting.data_sources.fia_business import count_all_districts


def test_count_all_districts_one_pass():
    rows = [
        ["營業地址", "其他"],                    # 表頭略過
        ["桃園市龜山區樂善里1號", "x"],
        ["桃園市龜山區山頂里2號", "x"],
        ["桃園市中壢區中央路3號", "x"],
        ["新北市板橋區4號", "x"],
    ]
    counts, total = count_all_districts(rows, ["龜山區", "中壢區", "大溪區"])
    assert counts == {"龜山區": 2, "中壢區": 1, "大溪區": 0}
    assert total == 4   # 全國總筆數（扣表頭）
