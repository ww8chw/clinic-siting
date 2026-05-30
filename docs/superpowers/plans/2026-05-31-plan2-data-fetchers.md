# 診所選址評估系統 — Plan 2：資料抓取層 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為六個已驗證可用的資料來源各建一個抓取器，把外部 API／開放資料轉成 Plan 1 的乾淨領域物件（Place / TransitStop / Clinic），供 Plan 3 管線彙總成 `normalized_factors`。

**Architecture:** 每個抓取器拆成兩半——`parse_*(raw)` 是純函式，吃已抓回的原始回應、吐領域物件，用真實 API fixture 做 TDD；`fetch_*(...)` 是薄 HTTP 層，負責組請求、認證、回傳原始 JSON/CSV。測試只測 parser（不需金鑰、決定性可重現）；fetch 以 `@pytest.mark.live` 標記、缺金鑰時自動 skip。所有環境變數從專案根 `.env` 載入。

**Tech Stack:** Python 3.9.6（**所有新模組檔頭必須有 `from __future__ import annotations`**，因 3.9 不支援 `X | Y` runtime union）、pytest、requests、python-dotenv、stdlib csv。距離/半徑沿用 Plan 1 的 `geo/`。

**已驗證的真實 API 事實（寫程式前必讀）：**
- Google Geocoding：`status=="OK"`，`results[0].geometry.location.{lat,lng}`、`results[0].formatted_address`。固定地址座標為 `(25.0461974, 121.3918275)`。
- Google Places (New v1)：`searchText` 與 `searchNearby` 回應同形，皆為 `{"places":[{displayName:{text}, types:[], rating, userRatingCount, location:{latitude,longitude}, formattedAddress}]}`；**零結果時回 `{}`（無 places 鍵）**。台灣診所 type 多為 `hospital`/`medical_center`/`health`，**非** `doctor`，所以競爭對手用 `searchText("診所")` 抓。
- Google Distance Matrix：`rows[].elements[].{status, distance:{value,text}, duration:{value,text}}`，value 單位為公尺／秒。
- TDX：OAuth realm 為 **`TDXConnect`**（非 `TDX`）；token 端點 `https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token`，`grant_type=client_credentials`，回 `access_token`（有效 86400 秒）。公車站查詢 `GET /api/basic/v2/Bus/Stop/City/Taoyuan?$spatialFilter=nearby(lat,lng,meters)&$format=JSON`，回 list，每筆 `{StopName:{Zh_tw,En}, StopPosition:{PositionLat,PositionLon}}`。
- OSM Overpass：`POST https://overpass-api.de/api/interpreter`，body 為 `data=` query；**必須帶 User-Agent header 否則 406**。回 `{"elements":[{type:"node", lat, lon, tags:{name,...}}]}`。
- 健保署診所 CSV：`https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-D21004-009`（全國約 16MB，UTF-8-BOM）。欄位：`醫事機構代碼,醫事機構名稱,醫事機構種類,電話,地址,分區業務組,特約類別,服務項目,診療科別,終止合約或歇業日期,固定看診時段,備註,縣市別代碼,合約起日`。**無經緯度**（Plan 3 再對篩選後的子集 geocode）；地址用全形數字；`診療科別` 以逗號分隔多科。

---

## File Structure

```
店面選擇/
├── requirements.txt                      # 加 requests、python-dotenv
├── src/clinic_siting/
│   ├── models.py                         # 既有；新增 Place / TransitStop / Clinic
│   ├── data_sources/
│   │   ├── __init__.py
│   │   ├── env.py                        # load .env、取金鑰
│   │   ├── http.py                       # get_json / post_json / get_text 薄封裝
│   │   ├── geocode.py                    # parse_geocode + fetch_geocode + SITE 常數
│   │   ├── google_places.py             # parse_places + fetch_search_text / fetch_search_nearby
│   │   ├── google_distance.py           # parse_distance + fetch_distance_matrix
│   │   ├── tdx_transit.py               # fetch_token + parse_bus_stops + fetch_bus_stops
│   │   ├── osm_poi.py                    # parse_overpass + fetch_overpass
│   │   └── nhi_clinics.py               # parse_nhi_csv + fetch_nhi_csv
└── tests/
    ├── fixtures/                         # 已存在：真實 API 回應樣本
    │   ├── geocode.json
    │   ├── places_searchtext_clinic.json
    │   ├── places_searchnearby_pharmacy.json
    │   ├── distance_matrix.json
    │   ├── tdx_bus_stops.json
    │   ├── overpass_convenience.json
    │   └── nhi_clinics_guishan_sample.csv
    └── data_sources/
        ├── test_geocode.py
        ├── test_google_places.py
        ├── test_google_distance.py
        ├── test_tdx_transit.py
        ├── test_osm_poi.py
        └── test_nhi_clinics.py
```

職責劃分：`env.py` 只管讀 `.env`；`http.py` 只管送請求與基本錯誤；各 `*.py` 抓取器只負責「自己這個來源」的 parse 與 fetch，彼此不相依。`parse_*` 完全純函式、可離線測試。

---

## Task 1: 依賴、環境載入、HTTP 薄封裝、領域模型

**Files:**
- Modify: `requirements.txt`
- Create: `src/clinic_siting/data_sources/__init__.py`（空字串）
- Create: `src/clinic_siting/data_sources/env.py`
- Create: `src/clinic_siting/data_sources/http.py`
- Modify: `src/clinic_siting/models.py`
- Test: `tests/data_sources/test_env_models.py`

- [ ] **Step 1: 更新 `requirements.txt`**

```text
PyYAML==6.0.2
pytest==8.3.4
requests==2.32.3
python-dotenv==1.0.1
```

- [ ] **Step 2: 安裝新依賴**

Run: `cd "/Users/chenhungwen/Claude/店面選擇" && .venv/bin/pip install -r requirements.txt`
Expected: 成功安裝 requests 與 python-dotenv。

- [ ] **Step 3: 寫失敗測試**

`tests/data_sources/test_env_models.py`:

```python
from clinic_siting.models import Place, TransitStop, Clinic


def test_place_defaults():
    p = Place(name="A", lat=25.0, lon=121.0, source="google")
    assert p.rating is None
    assert p.rating_count is None
    assert p.types == []


def test_transit_stop_fields():
    s = TransitStop(name="文林路口", lat=25.04, lon=121.39, kind="bus")
    assert s.kind == "bus"


def test_clinic_specialties_list():
    c = Clinic(code="X", name="某診所", kind="西醫診所",
               address="桃園市龜山區...", specialties=["家醫科", "不分科"])
    assert "家醫科" in c.specialties
    assert c.lat is None
```

- [ ] **Step 4: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_env_models.py -v`
Expected: FAIL，`ImportError: cannot import name 'Place'`

- [ ] **Step 5: 在 `models.py` 新增三個 dataclass**

在 `src/clinic_siting/models.py` 結尾追加（檔頭已有 `from __future__ import annotations`，勿移除）：

```python
@dataclass
class Place:
    name: str
    lat: float
    lon: float
    source: str                      # "google" | "osm"
    types: list[str] = field(default_factory=list)
    rating: float | None = None
    rating_count: int | None = None


@dataclass
class TransitStop:
    name: str
    lat: float
    lon: float
    kind: str                        # "bus" | "metro" | "youbike"


@dataclass
class Clinic:
    code: str
    name: str
    kind: str                        # 醫事機構種類，如「西醫診所」
    address: str
    specialties: list[str] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None
```

- [ ] **Step 6: 建立 `env.py`**

`src/clinic_siting/data_sources/env.py`:

```python
from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_env() -> dict[str, str]:
    """讀專案根 .env，回傳 dict（值為 None 的鍵會被濾掉）。"""
    return {k: v for k, v in dotenv_values(_ENV_PATH).items() if v}


def get_key(name: str) -> str | None:
    """取單一金鑰；不存在回 None（讓 fetch 層決定要不要 skip）。"""
    return load_env().get(name)
```

- [ ] **Step 7: 建立 `http.py`**

`src/clinic_siting/data_sources/http.py`:

```python
from __future__ import annotations

import requests

USER_AGENT = "clinic-siting/1.0 (research)"
DEFAULT_TIMEOUT = 30


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, params=params, headers=h, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def post_json(url: str, json_body: dict | None = None, data: dict | None = None,
              headers: dict | None = None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.post(url, json=json_body, data=data, headers=h, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, params: dict | None = None, headers: dict | None = None) -> str:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, params=params, headers=h, timeout=120)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text
```

- [ ] **Step 8: 建立空的 `data_sources/__init__.py`**

內容為空字串。

- [ ] **Step 9: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_env_models.py -v`
Expected: 3 passed

- [ ] **Step 10: Commit**

```bash
git add requirements.txt src/clinic_siting/models.py src/clinic_siting/data_sources/__init__.py src/clinic_siting/data_sources/env.py src/clinic_siting/data_sources/http.py tests/data_sources/test_env_models.py
git commit -m "feat: add data-source infra (env, http, domain models)"
```

---

## Task 2: 地理編碼（Google Geocoding）

**Files:**
- Create: `src/clinic_siting/data_sources/geocode.py`
- Test: `tests/data_sources/test_geocode.py`

- [ ] **Step 1: 寫失敗測試**（用真實 fixture `tests/fixtures/geocode.json`）

`tests/data_sources/test_geocode.py`:

```python
import json
from pathlib import Path

import pytest

from clinic_siting.data_sources.geocode import parse_geocode, SITE_LATLON, SITE_ADDRESS

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "geocode.json"


def test_parse_geocode_returns_latlon_and_address():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    lat, lon, formatted = parse_geocode(raw)
    assert 25.04 < lat < 25.05
    assert 121.39 < lon < 121.40
    assert "樂善二路503號" in formatted


def test_parse_geocode_raises_on_zero_results():
    with pytest.raises(ValueError):
        parse_geocode({"status": "ZERO_RESULTS", "results": []})


def test_site_constant_matches_known_point():
    assert abs(SITE_LATLON[0] - 25.0461974) < 1e-6
    assert "龜山" in SITE_ADDRESS
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_geocode.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `geocode.py`**

`src/clinic_siting/data_sources/geocode.py`:

```python
from __future__ import annotations

from clinic_siting.data_sources.http import get_json

SITE_ADDRESS = "桃園市龜山區樂善二路503號"
SITE_LATLON = (25.0461974, 121.3918275)  # 由 Google Geocoding 取得、寫死

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def parse_geocode(raw: dict) -> tuple[float, float, str]:
    """從 Google Geocoding 回應取 (lat, lon, formatted_address)。"""
    if raw.get("status") != "OK" or not raw.get("results"):
        raise ValueError(f"geocode 失敗: status={raw.get('status')}")
    r = raw["results"][0]
    loc = r["geometry"]["location"]
    return loc["lat"], loc["lng"], r["formatted_address"]


def fetch_geocode(address: str, api_key: str) -> dict:
    return get_json(_GEOCODE_URL, params={
        "address": address, "language": "zh-TW", "key": api_key,
    })
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_geocode.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/geocode.py tests/data_sources/test_geocode.py
git commit -m "feat: add Google geocoding fetcher and parser"
```

---

## Task 3: Google Places（競爭診所 + 互補錨點）

**Files:**
- Create: `src/clinic_siting/data_sources/google_places.py`
- Test: `tests/data_sources/test_google_places.py`

- [ ] **Step 1: 寫失敗測試**（用 `places_searchtext_clinic.json`、`places_searchnearby_pharmacy.json`）

`tests/data_sources/test_google_places.py`:

```python
import json
from pathlib import Path

from clinic_siting.data_sources.google_places import parse_places
from clinic_siting.models import Place

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_searchtext_clinics():
    raw = json.loads((FIX / "places_searchtext_clinic.json").read_text(encoding="utf-8"))
    places = parse_places(raw)
    assert len(places) >= 1
    p = places[0]
    assert isinstance(p, Place)
    assert p.source == "google"
    assert p.lat is not None and p.lon is not None
    assert p.name != ""


def test_parse_searchnearby_pharmacy_has_rating_count():
    raw = json.loads((FIX / "places_searchnearby_pharmacy.json").read_text(encoding="utf-8"))
    places = parse_places(raw)
    assert any(p.rating_count is not None for p in places)


def test_parse_empty_response_returns_empty_list():
    # Places New v1 零結果回 {}
    assert parse_places({}) == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_google_places.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `google_places.py`**

`src/clinic_siting/data_sources/google_places.py`:

```python
from __future__ import annotations

from clinic_siting.data_sources.http import post_json
from clinic_siting.models import Place

_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
_SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
_FIELD_MASK = ("places.displayName,places.types,places.rating,"
               "places.userRatingCount,places.location,places.formattedAddress")


def parse_places(raw: dict) -> list[Place]:
    """把 Places New v1 (searchText/searchNearby 同形) 轉成 Place list。
    零結果時回應為 {}，回傳空 list。"""
    out: list[Place] = []
    for p in raw.get("places", []):
        loc = p.get("location", {})
        out.append(Place(
            name=p.get("displayName", {}).get("text", ""),
            lat=loc.get("latitude"),
            lon=loc.get("longitude"),
            source="google",
            types=p.get("types", []),
            rating=p.get("rating"),
            rating_count=p.get("userRatingCount"),
        ))
    return out


def _headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _FIELD_MASK,
    }


def fetch_search_text(query: str, lat: float, lon: float, radius_m: int,
                      api_key: str, max_results: int = 20) -> dict:
    body = {
        "textQuery": query,
        "languageCode": "zh-TW",
        "maxResultCount": max_results,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                     "radius": radius_m}},
    }
    return post_json(_SEARCH_TEXT_URL, json_body=body, headers=_headers(api_key))


def fetch_search_nearby(included_types: list[str], lat: float, lon: float, radius_m: int,
                        api_key: str, max_results: int = 20) -> dict:
    body = {
        "includedTypes": included_types,
        "languageCode": "zh-TW",
        "maxResultCount": max_results,
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                            "radius": radius_m}},
    }
    return post_json(_SEARCH_NEARBY_URL, json_body=body, headers=_headers(api_key))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_google_places.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/google_places.py tests/data_sources/test_google_places.py
git commit -m "feat: add Google Places fetcher and parser"
```

---

## Task 4: Google Distance Matrix（車程可及性）

**Files:**
- Create: `src/clinic_siting/data_sources/google_distance.py`
- Test: `tests/data_sources/test_google_distance.py`

- [ ] **Step 1: 寫失敗測試**（用 `distance_matrix.json`）

`tests/data_sources/test_google_distance.py`:

```python
import json
from pathlib import Path

from clinic_siting.data_sources.google_distance import parse_distance

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "distance_matrix.json"


def test_parse_distance_returns_meters_and_seconds():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    results = parse_distance(raw)
    assert len(results) >= 1
    r = results[0]
    assert r["status"] == "OK"
    assert r["distance_m"] > 0
    assert r["duration_s"] > 0
    assert "公里" in r["distance_text"]


def test_parse_distance_handles_not_found_element():
    raw = {"rows": [{"elements": [{"status": "NOT_FOUND"}]}]}
    results = parse_distance(raw)
    assert results[0]["status"] == "NOT_FOUND"
    assert results[0]["distance_m"] is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_google_distance.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `google_distance.py`**

`src/clinic_siting/data_sources/google_distance.py`:

```python
from __future__ import annotations

from clinic_siting.data_sources.http import get_json

_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def parse_distance(raw: dict) -> list[dict]:
    """攤平 Distance Matrix 回應成 list；每筆含 status / distance_m / duration_s / 文字。
    非 OK 的 element 其數值欄位為 None。"""
    out: list[dict] = []
    for row in raw.get("rows", []):
        for el in row.get("elements", []):
            status = el.get("status")
            if status == "OK":
                out.append({
                    "status": status,
                    "distance_m": el["distance"]["value"],
                    "duration_s": el["duration"]["value"],
                    "distance_text": el["distance"]["text"],
                    "duration_text": el["duration"]["text"],
                })
            else:
                out.append({"status": status, "distance_m": None, "duration_s": None,
                            "distance_text": None, "duration_text": None})
    return out


def fetch_distance_matrix(origin: tuple[float, float],
                          destinations: list[tuple[float, float]],
                          api_key: str, mode: str = "driving") -> dict:
    dest_str = "|".join(f"{lat},{lon}" for lat, lon in destinations)
    return get_json(_URL, params={
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": dest_str,
        "mode": mode, "language": "zh-TW", "key": api_key,
    })
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_google_distance.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/google_distance.py tests/data_sources/test_google_distance.py
git commit -m "feat: add Google Distance Matrix fetcher and parser"
```

---

## Task 5: TDX 大眾運輸（公車站可及性）

**Files:**
- Create: `src/clinic_siting/data_sources/tdx_transit.py`
- Test: `tests/data_sources/test_tdx_transit.py`

- [ ] **Step 1: 寫失敗測試**（用 `tdx_bus_stops.json`）

`tests/data_sources/test_tdx_transit.py`:

```python
import json
from pathlib import Path

from clinic_siting.data_sources.tdx_transit import parse_bus_stops, TDX_TOKEN_URL
from clinic_siting.models import TransitStop

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "tdx_bus_stops.json"


def test_parse_bus_stops():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    stops = parse_bus_stops(raw)
    assert len(stops) >= 1
    s = stops[0]
    assert isinstance(s, TransitStop)
    assert s.kind == "bus"
    assert s.name != ""
    assert 25.0 < s.lat < 25.1
    assert 121.3 < s.lon < 121.5


def test_token_url_uses_tdxconnect_realm():
    # realm 必須是 TDXConnect（曾踩過 TDX realm 404 的坑）
    assert "TDXConnect" in TDX_TOKEN_URL


def test_parse_empty_list():
    assert parse_bus_stops([]) == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_tdx_transit.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `tdx_transit.py`**

`src/clinic_siting/data_sources/tdx_transit.py`:

```python
from __future__ import annotations

import requests

from clinic_siting.data_sources.http import USER_AGENT, get_json
from clinic_siting.models import TransitStop

TDX_TOKEN_URL = ("https://tdx.transportdata.tw/auth/realms/TDXConnect/"
                 "protocol/openid-connect/token")
_BUS_STOP_URL = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/{city}"


def parse_bus_stops(raw: list) -> list[TransitStop]:
    """把 TDX Bus/Stop 回應轉成 TransitStop list。"""
    out: list[TransitStop] = []
    for s in raw:
        pos = s.get("StopPosition", {})
        name = s.get("StopName", {}).get("Zh_tw", "")
        if pos.get("PositionLat") is None or pos.get("PositionLon") is None:
            continue
        out.append(TransitStop(name=name, lat=pos["PositionLat"],
                               lon=pos["PositionLon"], kind="bus"))
    return out


def fetch_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(TDX_TOKEN_URL, headers={"User-Agent": USER_AGENT}, data={
        "grant_type": "client_credentials",
        "client_id": client_id, "client_secret": client_secret,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_bus_stops(lat: float, lon: float, radius_m: int, token: str,
                    city: str = "Taoyuan", top: int = 50) -> list:
    url = _BUS_STOP_URL.format(city=city)
    return get_json(url, params={
        "$spatialFilter": f"nearby({lat},{lon},{radius_m})",
        "$format": "JSON", "$top": top,
    }, headers={"authorization": f"Bearer {token}"})
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_tdx_transit.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/tdx_transit.py tests/data_sources/test_tdx_transit.py
git commit -m "feat: add TDX transit fetcher and parser"
```

---

## Task 6: OSM Overpass（便利商店等 POI 免費備援）

**Files:**
- Create: `src/clinic_siting/data_sources/osm_poi.py`
- Test: `tests/data_sources/test_osm_poi.py`

- [ ] **Step 1: 寫失敗測試**（用 `overpass_convenience.json`）

`tests/data_sources/test_osm_poi.py`:

```python
import json
from pathlib import Path

from clinic_siting.data_sources.osm_poi import parse_overpass, build_query
from clinic_siting.models import Place

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "overpass_convenience.json"


def test_parse_overpass_nodes():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    places = parse_overpass(raw)
    assert len(places) >= 1
    p = places[0]
    assert isinstance(p, Place)
    assert p.source == "osm"
    assert p.lat is not None and p.lon is not None


def test_parse_overpass_empty():
    assert parse_overpass({"elements": []}) == []


def test_build_query_contains_filter_and_radius():
    q = build_query("shop", "convenience", 25.04, 121.39, 1000)
    assert "convenience" in q
    assert "around:1000" in q
    assert "[out:json]" in q
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_osm_poi.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `osm_poi.py`**

`src/clinic_siting/data_sources/osm_poi.py`:

```python
from __future__ import annotations

from clinic_siting.data_sources.http import post_json
from clinic_siting.models import Place

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query(key: str, value: str, lat: float, lon: float, radius_m: int) -> str:
    """組 Overpass QL：抓指定 tag 的 node，含 way/relation 的中心點。"""
    f = f'["{key}"="{value}"](around:{radius_m},{lat},{lon})'
    return (f"[out:json][timeout:25];"
            f"(node{f};way{f};relation{f};);out center;")


def parse_overpass(raw: dict) -> list[Place]:
    """把 Overpass 回應轉成 Place list；way/relation 取 center 座標。"""
    out: list[Place] = []
    for el in raw.get("elements", []):
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        out.append(Place(
            name=tags.get("name", ""),
            lat=lat, lon=lon, source="osm",
            types=[f"{k}={v}" for k, v in tags.items()
                   if k in ("shop", "amenity", "leisure", "healthcare")],
        ))
    return out


def fetch_overpass(query: str) -> dict:
    return post_json(_OVERPASS_URL, data={"data": query})
```

注意：`http.post_json` 已帶 User-Agent（避免 406）。`data={"data": query}` 會以 form-urlencoded 送出，符合 Overpass 介面。

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_osm_poi.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/osm_poi.py tests/data_sources/test_osm_poi.py
git commit -m "feat: add OSM Overpass POI fetcher and parser"
```

---

## Task 7: 健保署特約診所（權威競爭名冊 + 科別）

**Files:**
- Create: `src/clinic_siting/data_sources/nhi_clinics.py`
- Test: `tests/data_sources/test_nhi_clinics.py`

- [ ] **Step 1: 寫失敗測試**（用 `nhi_clinics_guishan_sample.csv`）

`tests/data_sources/test_nhi_clinics.py`:

```python
from pathlib import Path

from clinic_siting.data_sources.nhi_clinics import parse_nhi_csv
from clinic_siting.models import Clinic

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "nhi_clinics_guishan_sample.csv"


def test_parse_filters_by_district_keyword():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    assert len(clinics) >= 1
    assert all(isinstance(c, Clinic) for c in clinics)
    assert all("龜山" in c.address for c in clinics)


def test_specialties_split_into_list():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    # 至少一家有解析出多科別（fixture 內有「不分科,家醫科」）
    assert any(len(c.specialties) >= 2 for c in clinics)
    # 科別字串不應殘留逗號
    assert all("," not in s for c in clinics for s in c.specialties)


def test_filter_excludes_non_matching_district():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="不存在的地名XYZ")
    assert clinics == []


def test_kind_preserved():
    text = FIX.read_text(encoding="utf-8-sig")
    clinics = parse_nhi_csv(text, district_keyword="龜山")
    assert any("診所" in c.kind for c in clinics)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/data_sources/test_nhi_clinics.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `nhi_clinics.py`**

`src/clinic_siting/data_sources/nhi_clinics.py`:

```python
from __future__ import annotations

import csv
import io

from clinic_siting.data_sources.http import get_text
from clinic_siting.models import Clinic

NHI_CLINIC_CSV_URL = ("https://info.nhi.gov.tw/api/iode0000s01/Dataset"
                      "?rId=A21030000I-D21004-009")

# CSV 欄位索引（依健保署固定格式）
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/data_sources/test_nhi_clinics.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/nhi_clinics.py tests/data_sources/test_nhi_clinics.py
git commit -m "feat: add NHI clinic registry fetcher and parser"
```

---

## Task 8: 全套件驗證

- [ ] **Step 1: 跑整個測試套件**

Run: `cd "/Users/chenhungwen/Claude/店面選擇" && .venv/bin/pytest -q`
Expected: 全部 passed（Plan 1 的 23 個 + Plan 2 新增：env_models 3 + geocode 3 + places 3 + distance 2 + tdx 3 + osm 3 + nhi 4 = 21 個，共 44）。

- [ ] **Step 2:（可選）真實連線冒煙測試**

說明：此步驟需要 `.env` 內有金鑰，僅供人工驗證抓取器確實能連通，不納入自動套件。在專案根執行：

```bash
.venv/bin/python -c "
from clinic_siting.data_sources.env import get_key
from clinic_siting.data_sources.geocode import fetch_geocode, parse_geocode
k=get_key('GOOGLE_MAPS_API_KEY')
print(parse_geocode(fetch_geocode('桃園市龜山區樂善二路503號', k)))
"
```
Expected: 印出 `(25.04..., 121.39..., '...樂善二路503號')`。若無金鑰則跳過。

- [ ] **Step 3: 確認沒有把金鑰或大型資料 commit 進去**

Run: `git status --porcelain && git ls-files | grep -E "\.env$" || echo "OK: .env 未被追蹤"`
Expected: `.env` 不在版控；fixtures 為小樣本（非 16MB 全國檔）。

---

## 後續 Plan 路線圖

- **Plan 3 — 整合管線 + 快照**：orchestrator 串接本 Plan 抓取器 →（對 NHI 篩選後子集做 geocode）→ 雙半徑（步行 1km / 車程 3km）彙總成 `normalized_factors` → 評分 → 寫 `history.jsonl`；含群聚/稀釋判斷、互補錨點分類、資料缺漏的降級（沿用上次快照值並標註）。**參考資料庫（SEGIS 人口網格/晝夜、電子發票 B2C、營業稅籍、國土利用、實價屋齡）需使用者手動下載**，於 Plan 3 開始時提出清單。
- **Plan 4 — HTML 網站輸出**：Chart.js（雷達/趨勢/長條）+ Leaflet 地圖讀 `history.json`；手動加分欄位輸入介面。
- **Plan 5 — 自動化**：macOS launchd 每月觸發、推送網站、呼叫 n8n webhook 寄通知。
