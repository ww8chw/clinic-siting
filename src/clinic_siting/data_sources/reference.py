from __future__ import annotations

import csv
import io
from pathlib import Path

# 本地參考資料目錄（專案根 /data/reference）
REFERENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"

# 財政部村里所得 CSV 欄位
_INC_DISTRICT = "縣市別"      # 含「桃園市龜山區」
_INC_VILLAGE = "村里"
_INC_HOUSEHOLDS = "納稅單位(戶)"
_INC_MEAN = "平均數"
_INC_MEDIAN = "中位數"

# 桃園市人口 CSV 欄位
_POP_REGION = "區域別"
_POP_HOUSEHOLDS = "戶數"
_POP_POPULATION = "人口數"


def _to_int(s: str) -> int:
    s = (s or "").strip().replace(",", "")
    return int(s) if s else 0


def _rows(text: str):
    """DictReader，並把欄名殘留的 BOM/空白去掉（來源 CSV 首欄常帶 \ufeff）。"""
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        yield {(k or "").lstrip("\ufeff").strip(): v for k, v in row.items()}


def parse_income_csv(text: str) -> dict[str, dict]:
    """財政部村里綜所稅 CSV → {村里: {district, households, mean, median}}。"""
    out: dict[str, dict] = {}
    for row in _rows(text):
        village = (row.get(_INC_VILLAGE) or "").strip()
        if not village:
            continue
        out[village] = {
            "district": (row.get(_INC_DISTRICT) or "").strip(),
            "households": _to_int(row.get(_INC_HOUSEHOLDS)),
            "mean": _to_int(row.get(_INC_MEAN)),
            "median": _to_int(row.get(_INC_MEDIAN)),
        }
    return out


def parse_population_csv(text: str) -> dict[str, dict]:
    """桃園市人口 CSV → {區域別: {population, households}}。

    每區有兩列（性別 1/2），人口數加總；戶數僅出現在第一列。
    """
    reader = csv.DictReader(io.StringIO(text))
    out: dict[str, dict] = {}
    for row in reader:
        region = (row.get(_POP_REGION) or "").strip()
        if not region:
            continue
        agg = out.setdefault(region, {"population": 0, "households": 0})
        agg["population"] += _to_int(row.get(_POP_POPULATION))
        hh = _to_int(row.get(_POP_HOUSEHOLDS))
        if hh:
            agg["households"] = hh
    return out


def district_income_summary(income: dict[str, dict], district_prefix: str) -> dict:
    """聚合某行政區所有村里：戶數總和、戶數加權中位所得、村里數。"""
    villages = [v for v in income.values() if v["district"] == district_prefix]
    total_hh = sum(v["households"] for v in villages)
    if total_hh > 0:
        weighted_median = sum(v["median"] * v["households"] for v in villages) / total_hh
    else:
        weighted_median = 0.0
    return {
        "total_households": total_hh,
        "weighted_median": weighted_median,
        "village_count": len(villages),
    }
