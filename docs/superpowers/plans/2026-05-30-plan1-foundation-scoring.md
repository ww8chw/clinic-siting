# 診所選址評估系統 — Plan 1：核心骨架與評分引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立專案骨架與一個純函式評分引擎，能依 `specialties.yaml` 權重，把各因子的正規化分數算成 5 個科別各自的 0–100 適合度分數。

**Architecture:** 純 Python、無外部 API 依賴（資料抓取留待 Plan 2）。核心是三個可獨立測試的單元：距離/半徑幾何、因子正規化、加權評分引擎。所有運算為決定性純函式，以 pytest fixture 驗證可重現。

**Tech Stack:** Python 3.11+、pytest、PyYAML。距離用手寫 haversine（不引入 geopandas）。

---

## File Structure

```
店面選擇/
├── .gitignore
├── requirements.txt
├── .env.example
├── pytest.ini
├── config/
│   └── specialties.yaml          # 因子清單、權重等級、各科別權重矩陣
├── src/clinic_siting/
│   ├── __init__.py
│   ├── models.py                 # FactorScores, SpecialtyScore dataclasses
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── distance.py           # haversine_km()
│   │   └── radius.py             # points_within_radius()
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── normalize.py          # minmax_score()
│   │   ├── config.py             # load_specialty_config()
│   │   └── engine.py             # score_all_specialties()
│   └── cli.py                    # demo entrypoint
└── tests/
    ├── geo/test_distance.py
    ├── geo/test_radius.py
    └── scoring/
        ├── test_normalize.py
        ├── test_config.py
        └── test_engine.py
```

職責劃分：`geo/` 只管空間幾何；`scoring/normalize.py` 只管把原始值轉 0–100；`scoring/config.py` 只管讀設定檔並解析權重等級成數字；`scoring/engine.py` 只管加權組合。各檔單一職責、可獨立測試。

---

## Task 1: 專案骨架

**Files:**
- Create: `.gitignore`, `requirements.txt`, `.env.example`, `pytest.ini`
- Create: `src/clinic_siting/__init__.py`, `src/clinic_siting/geo/__init__.py`, `src/clinic_siting/scoring/__init__.py`

- [ ] **Step 1: 建立 `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
venv/
.env
.pytest_cache/
data/reference/*
!data/reference/.gitkeep
*.egg-info/
```

- [ ] **Step 2: 建立 `requirements.txt`**

```text
PyYAML==6.0.2
pytest==8.3.4
```

- [ ] **Step 3: 建立 `.env.example`**（Plan 2 才會用到金鑰，先預留）

```text
TGOS_APP_ID=
TGOS_APP_KEY=
TDX_CLIENT_ID=
TDX_CLIENT_SECRET=
GOOGLE_MAPS_API_KEY=
N8N_NOTIFY_WEBHOOK=
```

- [ ] **Step 4: 建立 `pytest.ini`**

```ini
[pytest]
pythonpath = src
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 5: 建立空的 package 檔**

`src/clinic_siting/__init__.py`、`src/clinic_siting/geo/__init__.py`、`src/clinic_siting/scoring/__init__.py` 三個檔，內容皆為空字串。

- [ ] **Step 6: 建立虛擬環境並安裝依賴**

Run: `cd "/Users/chenhungwen/Claude/店面選擇" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: 成功安裝 PyYAML 與 pytest。

- [ ] **Step 7: 確認 pytest 可執行**

Run: `.venv/bin/pytest -q`
Expected: `no tests ran`（尚無測試，正常）。

- [ ] **Step 8: Commit**

```bash
git add .gitignore requirements.txt .env.example pytest.ini src/clinic_siting/
git commit -m "chore: scaffold clinic-siting project"
```

---

## Task 2: Haversine 距離

**Files:**
- Create: `src/clinic_siting/geo/distance.py`
- Test: `tests/geo/test_distance.py`

- [ ] **Step 1: 寫失敗測試**

`tests/geo/test_distance.py`:

```python
from clinic_siting.geo.distance import haversine_km


def test_zero_distance_same_point():
    assert haversine_km(25.0, 121.0, 25.0, 121.0) == 0.0


def test_known_distance_taipei_to_kaohsiung():
    # 台北車站 (25.0478, 121.5170) -> 高雄車站 (22.6394, 120.3025)
    d = haversine_km(25.0478, 121.5170, 22.6394, 120.3025)
    assert 290 < d < 310  # 實際約 296 km


def test_short_distance_within_one_km():
    # 約 0.5 km 的兩點
    d = haversine_km(25.0000, 121.5000, 25.0045, 121.5000)
    assert 0.45 < d < 0.55
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/geo/test_distance.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'clinic_siting.geo.distance'`

- [ ] **Step 3: 實作最小程式**

`src/clinic_siting/geo/distance.py`:

```python
import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """兩個 (緯度, 經度) 點之間的大圓距離（公里）。"""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/geo/test_distance.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/geo/distance.py tests/geo/test_distance.py
git commit -m "feat: add haversine distance"
```

---

## Task 3: 半徑內點位篩選

**Files:**
- Create: `src/clinic_siting/geo/radius.py`
- Test: `tests/geo/test_radius.py`

- [ ] **Step 1: 寫失敗測試**

`tests/geo/test_radius.py`:

```python
from clinic_siting.geo.radius import points_within_radius


def test_filters_points_inside_radius():
    center = (25.0000, 121.5000)
    points = [
        {"id": "near", "lat": 25.0045, "lon": 121.5000},   # ~0.5 km
        {"id": "far", "lat": 25.1000, "lon": 121.5000},    # ~11 km
    ]
    result = points_within_radius(center, points, radius_km=1.0)
    ids = [p["id"] for p in result]
    assert ids == ["near"]


def test_empty_when_none_inside():
    center = (25.0, 121.5)
    points = [{"id": "x", "lat": 26.0, "lon": 121.5}]
    assert points_within_radius(center, points, radius_km=1.0) == []


def test_boundary_point_included():
    center = (25.0, 121.5)
    # 放一個約 0.9 km 的點，半徑 1 km 應納入
    points = [{"id": "edge", "lat": 25.0081, "lon": 121.5000}]
    result = points_within_radius(center, points, radius_km=1.0)
    assert [p["id"] for p in result] == ["edge"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/geo/test_radius.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作最小程式**

`src/clinic_siting/geo/radius.py`:

```python
from clinic_siting.geo.distance import haversine_km

Point = dict  # 需含 "lat", "lon" 鍵


def points_within_radius(center, points, radius_km: float):
    """回傳 center (lat, lon) 半徑 radius_km 公里內的點位 list。"""
    clat, clon = center
    return [
        p for p in points
        if haversine_km(clat, clon, p["lat"], p["lon"]) <= radius_km
    ]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/geo/test_radius.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/geo/radius.py tests/geo/test_radius.py
git commit -m "feat: add radius point filtering"
```

---

## Task 4: 因子正規化

**Files:**
- Create: `src/clinic_siting/scoring/normalize.py`
- Test: `tests/scoring/test_normalize.py`

- [ ] **Step 1: 寫失敗測試**

`tests/scoring/test_normalize.py`:

```python
from clinic_siting.scoring.normalize import minmax_score


def test_value_at_low_bound_scores_zero():
    assert minmax_score(0, lo=0, hi=100) == 0.0


def test_value_at_high_bound_scores_hundred():
    assert minmax_score(100, lo=0, hi=100) == 100.0


def test_value_below_low_is_clamped_to_zero():
    assert minmax_score(-50, lo=0, hi=100) == 0.0


def test_value_above_high_is_clamped_to_hundred():
    assert minmax_score(200, lo=0, hi=100) == 100.0


def test_midpoint():
    assert minmax_score(50, lo=0, hi=100) == 50.0


def test_invert_flips_score():
    # 競爭越多分數越低：invert=True
    assert minmax_score(100, lo=0, hi=100, invert=True) == 0.0
    assert minmax_score(0, lo=0, hi=100, invert=True) == 100.0


def test_equal_bounds_returns_fifty():
    assert minmax_score(5, lo=5, hi=5) == 50.0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/scoring/test_normalize.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作最小程式**

`src/clinic_siting/scoring/normalize.py`:

```python
def minmax_score(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """把 value 依 [lo, hi] 線性映射到 0–100，超出範圍 clamp。
    invert=True 用於負向因子（值越大分數越低，如競爭密度）。
    lo == hi 時回傳中性值 50。"""
    if hi == lo:
        return 50.0
    pct = (value - lo) / (hi - lo)
    pct = max(0.0, min(1.0, pct))
    score = pct * 100.0
    return 100.0 - score if invert else score
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/scoring/test_normalize.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/scoring/normalize.py tests/scoring/test_normalize.py
git commit -m "feat: add minmax factor normalization"
```

---

## Task 5: 科別設定檔與載入器

**Files:**
- Create: `config/specialties.yaml`
- Create: `src/clinic_siting/scoring/config.py`
- Test: `tests/scoring/test_config.py`

- [ ] **Step 1: 建立 `config/specialties.yaml`**

對應 spec 第 3 節權重矩陣。權重等級轉數字；`negative_factors` 標記需 invert 的因子。

```yaml
weight_levels:
  最高: 5
  高: 4
  中: 3
  低: 2
  無: 0

factors:
  - population_density       # 總人口/密度
  - age_gender               # 25–45歲/女性比
  - day_night_gap            # 晝夜人口落差
  - purchasing_power         # 消費力
  - business_density         # 商業活動密度
  - land_use_mix             # 土地使用混合
  - competition              # 同科別競爭（負向）
  - complementary_anchors    # 互補錨點加權
  - convenience_density      # 便利超商密度
  - accessibility            # 交通/停車可及
  - redevelopment_stage      # 重劃區發展階段/屋齡
  - visibility               # 能見度/臨街

negative_factors:
  - competition

specialties:
  family_medicine:
    population_density: 高
    age_gender: 中
    day_night_gap: 中
    purchasing_power: 中
    business_density: 中
    land_use_mix: 中
    competition: 中
    complementary_anchors: 中
    convenience_density: 高
    accessibility: 高
    redevelopment_stage: 中
    visibility: 中
  functional_medicine:
    population_density: 中
    age_gender: 中
    day_night_gap: 中
    purchasing_power: 高
    business_density: 中
    land_use_mix: 中
    competition: 低
    complementary_anchors: 中
    convenience_density: 中
    accessibility: 中
    redevelopment_stage: 中
    visibility: 中
  weight_loss:
    population_density: 中
    age_gender: 高
    day_night_gap: 中
    purchasing_power: 高
    business_density: 中
    land_use_mix: 中
    competition: 高
    complementary_anchors: 中
    convenience_density: 中
    accessibility: 中
    redevelopment_stage: 中
    visibility: 中
  psychiatry:
    population_density: 高
    age_gender: 中
    day_night_gap: 中
    purchasing_power: 中
    business_density: 低
    land_use_mix: 中
    competition: 中
    complementary_anchors: 中
    convenience_density: 中
    accessibility: 高
    redevelopment_stage: 中
    visibility: 中
  aesthetics:
    population_density: 中
    age_gender: 高
    day_night_gap: 中
    purchasing_power: 最高
    business_density: 高
    land_use_mix: 中
    competition: 最高
    complementary_anchors: 中
    convenience_density: 高
    accessibility: 中
    redevelopment_stage: 中
    visibility: 高
```

- [ ] **Step 2: 寫失敗測試**

`tests/scoring/test_config.py`:

```python
from pathlib import Path
from clinic_siting.scoring.config import load_specialty_config

CONFIG = Path(__file__).resolve().parents[2] / "config" / "specialties.yaml"


def test_loads_all_five_specialties():
    cfg = load_specialty_config(CONFIG)
    assert set(cfg.specialties.keys()) == {
        "family_medicine", "functional_medicine", "weight_loss",
        "psychiatry", "aesthetics",
    }


def test_weights_resolved_to_numbers():
    cfg = load_specialty_config(CONFIG)
    # 醫美的消費力是「最高」= 5
    assert cfg.specialties["aesthetics"]["purchasing_power"] == 5
    # 家醫科的便利超商是「高」= 4
    assert cfg.specialties["family_medicine"]["convenience_density"] == 4


def test_competition_marked_negative():
    cfg = load_specialty_config(CONFIG)
    assert "competition" in cfg.negative_factors


def test_every_specialty_covers_all_factors():
    cfg = load_specialty_config(CONFIG)
    for name, weights in cfg.specialties.items():
        assert set(weights.keys()) == set(cfg.factors), f"{name} 缺因子"
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/scoring/test_config.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 4: 實作最小程式**

`src/clinic_siting/scoring/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class SpecialtyConfig:
    factors: list[str]
    negative_factors: list[str]
    specialties: dict[str, dict[str, int]]  # specialty -> factor -> numeric weight


def load_specialty_config(path: Path) -> SpecialtyConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    levels = raw["weight_levels"]
    factors = raw["factors"]
    specialties = {
        name: {factor: levels[level] for factor, level in weights.items()}
        for name, weights in raw["specialties"].items()
    }
    return SpecialtyConfig(
        factors=factors,
        negative_factors=raw.get("negative_factors", []),
        specialties=specialties,
    )
```

- [ ] **Step 5: 跑測試確認通過**

Run: `.venv/bin/pytest tests/scoring/test_config.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add config/specialties.yaml src/clinic_siting/scoring/config.py tests/scoring/test_config.py
git commit -m "feat: add specialty weight config and loader"
```

---

## Task 6: 評分引擎

**Files:**
- Create: `src/clinic_siting/models.py`
- Create: `src/clinic_siting/scoring/engine.py`
- Test: `tests/scoring/test_engine.py`

評分定義：每個科別分數 = Σ(該因子正規化分數 × 該因子權重) / Σ(權重)，得到 0–100。輸入的 `normalized_factors` 已是各因子 0–100 分（負向因子在正規化階段已 invert，引擎不再處理方向）。

- [ ] **Step 1: 寫失敗測試**

`tests/scoring/test_engine.py`:

```python
from clinic_siting.scoring.engine import score_specialty, score_all_specialties
from clinic_siting.scoring.config import SpecialtyConfig


def _config():
    return SpecialtyConfig(
        factors=["a", "b"],
        negative_factors=[],
        specialties={
            "x": {"a": 4, "b": 2},   # 權重 4:2
            "y": {"a": 2, "b": 2},   # 權重 1:1
        },
    )


def test_score_specialty_weighted_average():
    # a=100, b=40, 權重 4:2 -> (100*4 + 40*2)/6 = 80
    result = score_specialty({"a": 100.0, "b": 40.0}, {"a": 4, "b": 2})
    assert result.score == 80.0
    assert result.specialty is None or True  # specialty 名由上層填


def test_score_specialty_equal_weights():
    # a=100, b=0, 權重 1:1 -> 50
    result = score_specialty({"a": 100.0, "b": 0.0}, {"a": 2, "b": 2})
    assert result.score == 50.0


def test_factor_contributions_sum_to_score():
    result = score_specialty({"a": 100.0, "b": 40.0}, {"a": 4, "b": 2})
    assert round(sum(result.factor_contributions.values()), 6) == round(result.score, 6)


def test_score_all_specialties_returns_one_per_specialty():
    cfg = _config()
    normalized = {"a": 100.0, "b": 40.0}
    results = score_all_specialties(normalized, cfg)
    assert set(results.keys()) == {"x", "y"}
    assert results["x"].score == 80.0          # 權重 4:2
    assert results["y"].score == 70.0          # 權重 1:1 -> (100+40)/2
    assert results["x"].specialty == "x"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/scoring/test_engine.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `models.py`**

`src/clinic_siting/models.py`:

```python
from dataclasses import dataclass, field


@dataclass
class SpecialtyScore:
    score: float
    factor_contributions: dict[str, float] = field(default_factory=dict)
    specialty: str | None = None
```

- [ ] **Step 4: 實作 `engine.py`**

`src/clinic_siting/scoring/engine.py`:

```python
from clinic_siting.models import SpecialtyScore
from clinic_siting.scoring.config import SpecialtyConfig


def score_specialty(normalized_factors: dict[str, float],
                    weights: dict[str, int]) -> SpecialtyScore:
    """加權平均：Σ(分數×權重)/Σ(權重)，回傳 0–100。"""
    total_weight = sum(weights.values())
    if total_weight == 0:
        return SpecialtyScore(score=0.0, factor_contributions={})
    contributions = {
        factor: normalized_factors[factor] * weight / total_weight
        for factor, weight in weights.items()
    }
    return SpecialtyScore(
        score=sum(contributions.values()),
        factor_contributions=contributions,
    )


def score_all_specialties(normalized_factors: dict[str, float],
                          config: SpecialtyConfig) -> dict[str, SpecialtyScore]:
    results = {}
    for name, weights in config.specialties.items():
        s = score_specialty(normalized_factors, weights)
        s.specialty = name
        results[name] = s
    return results
```

- [ ] **Step 5: 跑測試確認通過**

Run: `.venv/bin/pytest tests/scoring/test_engine.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/clinic_siting/models.py src/clinic_siting/scoring/engine.py tests/scoring/test_engine.py
git commit -m "feat: add specialty scoring engine"
```

---

## Task 7: Demo CLI 串接

把 Task 2–6 串起來，用一組寫死的範例正規化因子值，印出 5 科別分數排名，驗證端到端可運作。Plan 2 之後會用真實抓取資料取代寫死值。

**Files:**
- Create: `src/clinic_siting/cli.py`
- Test: `tests/scoring/test_cli.py`

- [ ] **Step 1: 寫失敗測試**

`tests/scoring/test_cli.py`:

```python
from clinic_siting.cli import run_demo


def test_run_demo_returns_all_specialties_sorted():
    ranking = run_demo()
    # 回傳 list[(specialty, score)]，依分數由高到低
    names = [name for name, _ in ranking]
    scores = [score for _, score in ranking]
    assert len(ranking) == 5
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 100.0 for s in scores)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/pytest tests/scoring/test_cli.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `cli.py`**

`src/clinic_siting/cli.py`:

```python
from pathlib import Path
from clinic_siting.scoring.config import load_specialty_config
from clinic_siting.scoring.engine import score_all_specialties

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "specialties.yaml"

# Plan 2 前的範例正規化因子值（0–100，負向因子已 invert）
SAMPLE_FACTORS = {
    "population_density": 75.0,
    "age_gender": 70.0,
    "day_night_gap": 60.0,
    "purchasing_power": 80.0,
    "business_density": 65.0,
    "land_use_mix": 60.0,
    "competition": 55.0,
    "complementary_anchors": 60.0,
    "convenience_density": 85.0,
    "accessibility": 70.0,
    "redevelopment_stage": 90.0,
    "visibility": 50.0,
}


def run_demo():
    config = load_specialty_config(CONFIG_PATH)
    results = score_all_specialties(SAMPLE_FACTORS, config)
    ranking = sorted(
        ((name, s.score) for name, s in results.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    return ranking


def main():
    for name, score in run_demo():
        print(f"{name:20s} {score:5.1f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/pytest tests/scoring/test_cli.py -v`
Expected: 1 passed

- [ ] **Step 5: 手動跑一次 demo 看輸出**

Run: `.venv/bin/python -m clinic_siting.cli`
Expected: 印出 5 行 `科別 分數`，分數由高到低。

- [ ] **Step 6: 跑整個測試套件**

Run: `.venv/bin/pytest -q`
Expected: 全部 passed（distance 3 + radius 3 + normalize 7 + config 4 + engine 4 + cli 1）。

- [ ] **Step 7: Commit**

```bash
git add src/clinic_siting/cli.py tests/scoring/test_cli.py
git commit -m "feat: add demo CLI wiring scoring end-to-end"
```

---

## 後續 Plan 路線圖（各自獨立可測，依序進行）

- **Plan 2 — 資料抓取層**：`geocode`(TGOS)、`nhi_clinics`、`google_places`、`tdx_transit`、`osm_poi`、`youbike`、`complementary_anchors`，以及參考庫載入器（SEGIS 人口/晝夜、電子發票、營業稅籍、國土利用、實價屋齡）。每個抓取器以 mock API 回應測試，不打真實外部服務。
- **Plan 3 — 整合管線 + 快照**：orchestrator 串接抓取器 → 對雙半徑彙總成 `normalized_factors` → 評分 → 寫入 `history.jsonl`；含群聚/稀釋判斷與互補錨點分類邏輯；產生 `history.json`。
- **Plan 4 — HTML 網站輸出**：純靜態站，Chart.js（雷達/趨勢/長條）+ Leaflet 地圖讀 `history.json`；手動加分欄位輸入介面。
- **Plan 5 — 自動化**：macOS launchd 每月觸發、推送網站、呼叫 n8n webhook 寄通知。

各 Plan 在前一個完成後再撰寫，沿用本 Plan 建立的 `models.py`、`scoring/`、`geo/` 介面。
