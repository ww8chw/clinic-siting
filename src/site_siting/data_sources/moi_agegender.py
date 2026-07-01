"""內政部戶政司 ODRP052「現住人口數按性別、年齡及婚姻狀況分(村里)」。

提供村里級的年齡×性別人口（跨婚姻狀況加總），算出
壯年(25–49)占比與女性占比，餵給 age_gender 因子。
資料按 district_code 排序分頁，故用二分搜尋定位行政區頁塊，
只抓該區數頁（每頁約 380KB）而非整檔。
"""
from __future__ import annotations

import json
import urllib.request

BASE = "https://www.ris.gov.tw/rs-opendata/api/v1/datastore/ODRP052"
DEFAULT_YEAR = "114"

# 壯年消費客群（25–49 歲），對 減重/醫美 等自費科別最具價值
PRIME_AGES = {"25~29歲", "30~34歲", "35~39歲", "40~44歲", "45~49歲"}


def build_url(year: str, page: int) -> str:
    return f"{BASE}/{year}?page={page}"


def fetch_page(year: str, page: int) -> dict:
    req = urllib.request.Request(
        build_url(year, page), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        # 串流讀取偶會截斷，先讀完整 body 再解析
        return json.loads(r.read())


def aggregate_shares(rows: list[dict], site_id: str, village: str) -> dict | None:
    """跨婚姻狀況加總某村里的 (年齡,性別) 人口，回傳占比。

    找不到該村里任何資料 → None。"""
    total = 0
    female = 0
    prime = 0
    matched = False
    for x in rows:
        if x.get("site_id") != site_id or x.get("village") != village:
            continue
        matched = True
        pop = int(x.get("population") or 0)
        total += pop
        if x.get("sex") == "女":
            female += pop
        if x.get("age") in PRIME_AGES:
            prime += pop
    if not matched or total == 0:
        return None
    return {
        "total": total,
        "female_share": female / total,
        "prime_share": prime / total,
    }


def collect_village_shares(site_id: str, village: str,
                           year: str = DEFAULT_YEAR, fetch=fetch_page,
                           hint_page: int = 239) -> dict | None:
    """以候選里所在頁為中心向外擴張掃描，收齊該村里資料並算占比。

    rs-opendata 依「行政區序」（非 district_code 數值序）分頁，故無法二分
    搜尋；改以 hint_page 為中心擴張，找不到再漸進放大到全集（年度更新導致
    頁位漂移時可自癒）。已掃頁面快取，放大時不重抓。最後一頁偶有壞 JSON，
    交給逐頁 try/except 略過。"""
    meta = fetch(year, 1)
    total = int(meta.get("totalPage") or 1)
    cache: dict[int, list] = {}

    def page_rows(p: int) -> list:
        if p not in cache:
            try:
                cache[p] = fetch(year, p).get("responseData") or []
            except Exception:
                cache[p] = []
        return cache[p]

    for radius in (6, 20, total):
        lo = max(1, hint_page - radius)
        hi = min(total, hint_page + radius)
        rows: list[dict] = []
        for p in range(lo, hi + 1):
            rows.extend(page_rows(p))
        shares = aggregate_shares(rows, site_id, village)
        if shares is not None:
            return shares
    return None
