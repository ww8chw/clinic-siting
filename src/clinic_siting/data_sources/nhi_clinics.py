from __future__ import annotations

import csv
import io

from clinic_siting.data_sources.http import get_text
from clinic_siting.models import Clinic

NHI_CLINIC_CSV_URL = ("https://info.nhi.gov.tw/api/iode0000s01/Dataset"
                      "?rId=A21030000I-D21004-009")

# CSV 欄位名稱（依健保署固定格式）
_COL_CODE = "醫事機構代碼"
_COL_NAME = "醫事機構名稱"
_COL_KIND = "醫事機構種類"
_COL_ADDR = "地址"
_COL_SPEC = "診療科別"


def _split_specialties(raw: str) -> list[str]:
    """診療科別以逗號或頓號分隔，去空白與空項。"""
    parts: list[str] = []
    for chunk in raw.replace("、", ",").split(","):
        s = chunk.strip()
        if s:
            parts.append(s)
    return parts


def parse_nhi_csv(text: str, district_keyword: str) -> list[Clinic]:
    """解析健保署診所 CSV，只留地址含 district_keyword 的機構。"""
    reader = csv.DictReader(io.StringIO(text))
    out: list[Clinic] = []
    for row in reader:
        addr = (row.get(_COL_ADDR) or "").strip()
        if district_keyword not in addr:
            continue
        out.append(Clinic(
            code=(row.get(_COL_CODE) or "").strip(),
            name=(row.get(_COL_NAME) or "").strip(),
            kind=(row.get(_COL_KIND) or "").strip(),
            address=addr,
            specialties=_split_specialties(row.get(_COL_SPEC) or ""),
        ))
    return out


def fetch_nhi_csv() -> str:
    """下載全國診所 CSV（約 16MB），回傳文字。"""
    return get_text(NHI_CLINIC_CSV_URL)
