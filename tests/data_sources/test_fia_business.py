from clinic_siting.data_sources.fia_business import (
    count_in_rows,
    business_ratio,
)

ROWS = [
    ["營業地址", "統一編號", "營業人名稱"],            # 表頭略過
    ["桃園市龜山區樂善二路1號", "1", "A"],
    ["桃園市龜山區文化一路2號", "2", "B"],
    ["臺北市大安區3號", "3", "C"],
    ["新北市板橋區4號", "4", "D"],
    [],                                                # 空列略過
]


def test_count_in_rows_skips_header_and_blank():
    d, total = count_in_rows(ROWS, "龜山區")
    assert d == 2
    assert total == 4


def test_business_ratio_relative_to_national():
    # 行政區每千人家數 = 全國每千人家數 → 比值 1.0
    r = business_ratio(district_count=100, total=1000,
                       district_pop=10_000, national_pop=100_000)
    assert r == 1.0


def test_business_ratio_below_average_when_residential():
    # 居住型：家數占比低於全國 → 比值 < 1
    r = business_ratio(district_count=50, total=1000,
                       district_pop=10_000, national_pop=100_000)
    assert r < 1.0


def test_business_ratio_none_on_missing_data():
    assert business_ratio(10, 0, 100, 100) is None
    assert business_ratio(10, 100, 0, 100) is None
