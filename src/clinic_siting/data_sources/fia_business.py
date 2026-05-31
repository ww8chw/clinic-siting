"""財政部 全國營業(稅籍)登記資料（dataset 9400）。

以行政區營業家數/人口（每千人）相對全國平均的比值，作為晝夜人口
落差代理：比值≈1 表示日間就業活動與居住人口相稱；遠低於 1 為純住
宅型睡城（日間外移），遠高於 1 為商辦/就業聚集型（夜間清空）。
整檔約 320MB，採串流逐列過濾，不全載入記憶體。
"""
from __future__ import annotations

import csv
import io
import urllib.request

BUSINESS_CSV_URL = "https://eip.fia.gov.tw/data/BGMOPEN1.csv"
_ADDRESS_COL = 0   # 營業地址


def count_in_rows(rows, district: str) -> tuple[int, int]:
    """逐列計數：回傳 (該行政區家數, 全國總家數)。

    rows：CSV reader 產生的 list（含表頭，第一列略過）。"""
    district_count = 0
    total = 0
    for i, row in enumerate(rows):
        if i == 0 or not row:
            continue
        total += 1
        if district in (row[_ADDRESS_COL] if len(row) > _ADDRESS_COL else ""):
            district_count += 1
    return district_count, total


def business_ratio(district_count: int, total: int,
                   district_pop: int, national_pop: int) -> float | None:
    """行政區每千人家數 ÷ 全國每千人家數。資料不足 → None。"""
    if not (district_pop and national_pop and total):
        return None
    local_per_capita = district_count / district_pop
    national_per_capita = total / national_pop
    if national_per_capita == 0:
        return None
    return local_per_capita / national_per_capita


def fetch_counts(district: str, url: str = BUSINESS_CSV_URL) -> tuple[int, int]:
    """串流下載並計數該行政區與全國營業家數。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        buf = io.TextIOWrapper(r, encoding="utf-8", errors="replace")
        reader = csv.reader(buf)
        return count_in_rows(reader, district)
