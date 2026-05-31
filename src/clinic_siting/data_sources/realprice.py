from __future__ import annotations

import csv
import io
import re
import zipfile
from statistics import median

import requests

from clinic_siting.data_sources.http import USER_AGENT

# 內政部不動產交易實價查詢服務網——分季全國大量下載
_DOWNLOAD_URL = "https://plvr.land.moi.gov.tw/DownloadSeason"
# 桃園市買賣主檔（縣市代碼 h）。a=買賣、b=預售、c=租賃。
_CITY_MAIN_FILE = "h_lvr_land_a.csv"
_ROC_OFFSET = 1911


def roc_to_year(roc_date) -> int | None:
    """民國年月日字串（如 1130305 / 0950601）→ 西元年。無效回 None。"""
    digits = re.sub(r"\D", "", roc_date or "")
    if len(digits) < 5:           # 至少 YYYMM 或 YYMMDD 才取得到年
        return None
    return int(digits[:-4]) + _ROC_OFFSET


def _rows(text: str):
    """DictReader，並去掉欄名殘留的 BOM/空白。"""
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        yield {(k or "").lstrip("\ufeff").strip(): v for k, v in row.items()}


def parse_lvr_main_csv(text: str) -> list[dict]:
    """實價登錄主檔 CSV → [{district, address, txn_date, completion_date, type}]。

    第 1 列為中文欄名（DictReader 表頭），第 2 列為英文欄名（跳過）。"""
    out: list[dict] = []
    for row in _rows(text):
        district = (row.get("鄉鎮市區") or "").strip()
        if not district or district == "district":   # 跳過英文表頭列
            continue
        out.append({
            "district": district,
            "address": (row.get("土地位置建物門牌") or "").strip(),
            "txn_date": (row.get("交易年月日") or "").strip(),
            "completion_date": (row.get("建築完成年月") or "").strip(),
            "type": (row.get("建物型態") or "").strip(),
        })
    return out


def district_median_building_age(records: list[dict], district: str,
                                 as_of_year: int) -> float | None:
    """某行政區成交案件的屋齡中位數（年）。無有效資料回 None。"""
    ages = []
    for r in records:
        if r["district"] != district:
            continue
        year = roc_to_year(r["completion_date"])
        if year is None:
            continue
        age = as_of_year - year
        if age >= 0:
            ages.append(age)
    return float(median(ages)) if ages else None


def recent_seasons(year: int, month: int, n: int = 3) -> list[str]:
    """回推最近 n 個「已完成」的實價登錄季別字串（民國年Sx），最新在前。"""
    roc = year - _ROC_OFFSET
    quarter = (month - 1) // 3 + 1
    # 最近已完成季 = 當季 - 1
    quarter -= 1
    if quarter == 0:
        quarter = 4
        roc -= 1
    out = []
    for _ in range(n):
        out.append(f"{roc}S{quarter}")
        quarter -= 1
        if quarter == 0:
            quarter = 4
            roc -= 1
    return out


def fetch_lvr_main_csv(season: str) -> str:
    """下載某季全國 ZIP，回傳桃園市買賣主檔 CSV 文字（UTF-8）。"""
    resp = requests.get(
        _DOWNLOAD_URL,
        params={"season": season, "fileName": "lvr_landcsv.zip"},
        headers={"User-Agent": USER_AGENT},
        timeout=120,
    )
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        return zf.read(_CITY_MAIN_FILE).decode("utf-8-sig")
