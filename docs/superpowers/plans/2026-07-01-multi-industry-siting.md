# 多行業選址系統 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把診所選址系統泛化為固定地點下的多行業選址系統，行業以設定檔驅動，地點因子全行業共用，各行業只疊競爭池/錨點/權重。

**Architecture:** 收集層拆成 `collect_location`（11 個地點因子，每次刷新算一次）與 `collect_industry`（依 profile 掃競爭池與互補錨點）。競爭者來源以 adapter 分派（google_places / osm）。競爭因子改為每 profile 宣告 1..n 池、取最嚴格（最低分）。快照 schema 改為 location + industries 兩層。診所科別收編為 medical group，行為以回歸測試保證不變。套件更名（clinic_siting → site_siting）列為最後一個獨立任務。

**Tech Stack:** Python 3, PyYAML, pytest；前端純 HTML/CSS/JS + Leaflet。

**參考規格：** `docs/superpowers/specs/2026-07-01-multi-industry-siting-design.md`

---

## File Structure

- `config/industries.yaml`（新增，取代 `specialties.yaml`）— 行業設定：group/label/competitors/anchors/weights。
- `src/clinic_siting/scoring/config.py`（改）— 新增 `IndustryConfig` dataclass 與 `load_industry_config`。
- `src/clinic_siting/scoring/engine.py`（改）— `score_all_industries`。
- `src/clinic_siting/analysis/factors.py`（改）— 競爭多池取 min、`ALL_FACTORS` 移除 `competition_aesthetic`、`build_factors` 吃池列表。
- `src/clinic_siting/data_sources/competitors.py`（新增）— 競爭者/錨點來源 adapter（google_places / osm）。
- `src/clinic_siting/pipeline.py`（改）— `collect_location`、`collect_industry`、`run_pipeline` 迴圈行業、新快照 schema。
- `src/clinic_siting/snapshot.py`（改）— `fill_degraded` 支援單一因子 dict（沿用）。
- `src/clinic_siting/site_export.py`（改）— 讀 industries 層、分組輸出。
- `site/index.html`、`site/app.js`（改）— 行業組切換。
- `src/clinic_siting/runner.py`、`cli.py`（改）— 指向 industries.yaml。
- 測試：`tests/scoring/`、`tests/analysis/`、`tests/data_sources/`、`tests/test_pipeline.py`、`tests/test_site_export.py`。

## 快照 schema（新，所有任務共用契約）

```json
{
  "date": "2026-07-01",
  "location": {
    "factors": { "population_density": {"score": 75.0, "source": "real"}, "...11 個地點因子": {} },
    "raw": { "population": 180000, "...": "地點原始值" }
  },
  "industries": {
    "family_medicine": {
      "group": "medical",
      "label": "家醫科",
      "score": 72.3,
      "factors": { "...完整 13 因子（地點 11 + competition + complementary_anchors）": {} },
      "raw": { "competition_pools": [{"pool":"western","count":8,"weighted":5.2}], "anchor_count": 6, "anchor_weighted": 4.1 },
      "geo": { "competitors": [], "anchors": [] }
    }
  }
}
```

地點因子在 `location.factors`；每個 industry 的 `factors` 為「地點因子 + 該行業競爭/錨點因子」合併後的完整集合（供計分與明細表直接使用）。

---

## Task 1: 新增 industries.yaml 設定檔

**Files:**
- Create: `config/industries.yaml`

- [ ] **Step 1: 寫設定檔**

沿用 `weight_levels` 與 `negative_factors`；`factors` 移除 `competition_aesthetic`（13 因子）。每個 industry 有 `group`/`label`/`competitors`/`anchors`/`weights`。醫療 5 科的 `weights` 完全對映現有 `config/specialties.yaml`（aesthetics 的 `competition_aesthetic` 權重移到第二競爭池，見 Task 3 計分）。

```yaml
weight_levels: {最高: 5, 高: 4, 中: 3, 低: 2, 無: 0}

factors:
  - population_density
  - age_gender
  - day_night_gap
  - school_proximity
  - purchasing_power
  - business_density
  - land_use_mix
  - competition
  - complementary_anchors
  - convenience_density
  - accessibility
  - redevelopment_stage
  - visibility

negative_factors: [competition]

industries:
  family_medicine:
    group: medical
    label: 家醫科
    competitors:
      - {source: google_places, pool: western, types: [doctor, medical_clinic], classify: western}
    anchors: {source: google_places, types: [pharmacy, hospital]}
    weights: {population_density: 高, age_gender: 中, day_night_gap: 中, school_proximity: 高, purchasing_power: 中, business_density: 中, land_use_mix: 中, competition: 中, complementary_anchors: 中, convenience_density: 高, accessibility: 高, redevelopment_stage: 中, visibility: 中}
  functional_medicine:
    group: medical
    label: 功能醫學
    competitors:
      - {source: google_places, pool: western, types: [doctor, medical_clinic], classify: western}
    anchors: {source: google_places, types: [pharmacy, hospital]}
    weights: {population_density: 中, age_gender: 中, day_night_gap: 中, school_proximity: 無, purchasing_power: 高, business_density: 中, land_use_mix: 中, competition: 低, complementary_anchors: 中, convenience_density: 中, accessibility: 中, redevelopment_stage: 中, visibility: 中}
  weight_loss:
    group: medical
    label: 減重
    competitors:
      - {source: google_places, pool: western, types: [doctor, medical_clinic], classify: western}
    anchors: {source: google_places, types: [pharmacy, hospital]}
    weights: {population_density: 中, age_gender: 高, day_night_gap: 中, school_proximity: 中, purchasing_power: 高, business_density: 中, land_use_mix: 中, competition: 高, complementary_anchors: 中, convenience_density: 中, accessibility: 中, redevelopment_stage: 中, visibility: 中}
  psychiatry:
    group: medical
    label: 精神科
    competitors:
      - {source: google_places, pool: western, types: [doctor, medical_clinic], classify: western}
    anchors: {source: google_places, types: [pharmacy, hospital]}
    weights: {population_density: 高, age_gender: 中, day_night_gap: 中, school_proximity: 低, purchasing_power: 中, business_density: 低, land_use_mix: 中, competition: 中, complementary_anchors: 中, convenience_density: 中, accessibility: 高, redevelopment_stage: 中, visibility: 中}
  aesthetics:
    group: medical
    label: 醫美
    competitors:
      - {source: google_places, pool: western, types: [doctor, medical_clinic], classify: western}
      - {source: google_places, pool: aesthetic, types: [beauty_salon, spa, skin_care_clinic], classify: aesthetic}
    anchors: {source: google_places, types: [pharmacy, hospital]}
    weights: {population_density: 中, age_gender: 高, day_night_gap: 中, school_proximity: 中, purchasing_power: 最高, business_density: 高, land_use_mix: 中, competition: 最高, complementary_anchors: 中, convenience_density: 高, accessibility: 中, redevelopment_stage: 中, visibility: 高}
  restaurant:
    group: food
    label: 餐飲
    competitors:
      - {source: osm, tags: {amenity: restaurant}}
    anchors: {source: osm, tags: {shop: convenience}}
    weights: {population_density: 高, age_gender: 中, day_night_gap: 中, school_proximity: 中, purchasing_power: 中, business_density: 高, land_use_mix: 高, competition: 中, complementary_anchors: 中, convenience_density: 中, accessibility: 高, redevelopment_stage: 低, visibility: 高}
  bubble_tea:
    group: food
    label: 手搖飲
    competitors:
      - {source: google_places, types: [cafe], keywords: [手搖, 茶飲, 五十嵐, 清心, 迷客夏, coco]}
    anchors: {source: osm, tags: {amenity: school}}
    weights: {population_density: 高, age_gender: 高, day_night_gap: 中, school_proximity: 高, purchasing_power: 低, business_density: 高, land_use_mix: 中, competition: 高, complementary_anchors: 中, convenience_density: 高, accessibility: 高, redevelopment_stage: 低, visibility: 最高}
  cafe:
    group: food
    label: 咖啡
    competitors:
      - {source: osm, tags: {amenity: cafe}}
    anchors: {source: osm, tags: {amenity: coworking_space}}
    weights: {population_density: 中, age_gender: 高, day_night_gap: 中, school_proximity: 低, purchasing_power: 高, business_density: 高, land_use_mix: 高, competition: 中, complementary_anchors: 中, convenience_density: 中, accessibility: 中, redevelopment_stage: 中, visibility: 高}
  gym:
    group: fitness
    label: 健身房
    competitors:
      - {source: osm, tags: {leisure: fitness_centre}}
    anchors: {source: osm, tags: {shop: convenience}}
    weights: {population_density: 高, age_gender: 高, day_night_gap: 中, school_proximity: 低, purchasing_power: 高, business_density: 中, land_use_mix: 中, competition: 高, complementary_anchors: 中, convenience_density: 中, accessibility: 高, redevelopment_stage: 中, visibility: 高}
  cram_school:
    group: education
    label: 補習班
    competitors:
      - {source: osm, tags: {amenity: school}}
    anchors: {source: osm, tags: {amenity: school}}
    weights: {population_density: 高, age_gender: 中, day_night_gap: 中, school_proximity: 最高, purchasing_power: 高, business_density: 中, land_use_mix: 中, competition: 中, complementary_anchors: 高, convenience_density: 中, accessibility: 高, redevelopment_stage: 中, visibility: 中}
  hair_beauty:
    group: service
    label: 美容美髮
    competitors:
      - {source: osm, tags: {shop: hairdresser}}
    anchors: {source: osm, tags: {shop: convenience}}
    weights: {population_density: 中, age_gender: 高, day_night_gap: 中, school_proximity: 低, purchasing_power: 高, business_density: 中, land_use_mix: 中, competition: 中, complementary_anchors: 中, convenience_density: 中, accessibility: 中, redevelopment_stage: 中, visibility: 高}
```

- [ ] **Step 2: Commit**

```bash
git add config/industries.yaml
git commit -m "feat: 新增 industries.yaml 多行業設定檔（醫療收編＋6 新行業）"
```

---

## Task 2: IndustryConfig 與 load_industry_config

**Files:**
- Modify: `src/clinic_siting/scoring/config.py`
- Test: `tests/scoring/test_industry_config.py`

- [ ] **Step 1: 寫失敗測試**

```python
from pathlib import Path
from clinic_siting.scoring.config import load_industry_config

CONFIG = Path(__file__).resolve().parents[2] / "config" / "industries.yaml"


def test_loads_all_industries():
    cfg = load_industry_config(CONFIG)
    assert set(cfg.industries) >= {
        "family_medicine", "aesthetics", "restaurant", "bubble_tea",
        "cafe", "gym", "cram_school", "hair_beauty",
    }


def test_weights_mapped_to_numbers():
    cfg = load_industry_config(CONFIG)
    fam = cfg.industries["family_medicine"]
    assert fam.weights["accessibility"] == 4   # 高
    assert fam.weights["competition"] == 3      # 中


def test_competitor_pools_parsed():
    cfg = load_industry_config(CONFIG)
    aes = cfg.industries["aesthetics"]
    assert len(aes.competitors) == 2
    assert {p["pool"] for p in aes.competitors} == {"western", "aesthetic"}
    bt = cfg.industries["bubble_tea"].competitors[0]
    assert bt["source"] == "google_places"
    assert "手搖" in bt["keywords"]


def test_group_and_label():
    cfg = load_industry_config(CONFIG)
    assert cfg.industries["restaurant"].group == "food"
    assert cfg.industries["restaurant"].label == "餐飲"


def test_groups_helper():
    cfg = load_industry_config(CONFIG)
    groups = cfg.groups()
    assert "medical" in groups and "food" in groups
    assert "family_medicine" in groups["medical"]
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/scoring/test_industry_config.py -v`
Expected: FAIL（`load_industry_config` 不存在）

- [ ] **Step 3: 實作**

在 `src/clinic_siting/scoring/config.py` 末端新增（保留現有 `SpecialtyConfig`/`load_specialty_config` 不動，供 Task 9 前的相容）：

```python
@dataclass
class IndustryProfile:
    id: str
    group: str
    label: str
    competitors: list[dict]      # 每池: {source, pool?, types?, tags?, keywords?, classify?}
    anchors: dict                # {source, types?/tags?}
    weights: dict[str, int]      # factor -> numeric weight


@dataclass
class IndustryConfig:
    factors: list[str]
    negative_factors: list[str]
    industries: dict[str, IndustryProfile]

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for iid, p in self.industries.items():
            out.setdefault(p.group, []).append(iid)
        return out


def load_industry_config(path: Path) -> IndustryConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    levels = raw["weight_levels"]
    profiles: dict[str, IndustryProfile] = {}
    for iid, body in raw["industries"].items():
        profiles[iid] = IndustryProfile(
            id=iid,
            group=body["group"],
            label=body["label"],
            competitors=body.get("competitors", []),
            anchors=body.get("anchors", {}),
            weights={f: levels[lv] for f, lv in body["weights"].items()},
        )
    return IndustryConfig(
        factors=raw["factors"],
        negative_factors=raw.get("negative_factors", []),
        industries=profiles,
    )
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/scoring/test_industry_config.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/scoring/config.py tests/scoring/test_industry_config.py
git commit -m "feat: IndustryConfig 與 load_industry_config 載入行業設定"
```

---

## Task 3: 競爭多池取最嚴格 + 移除 competition_aesthetic

**Files:**
- Modify: `src/clinic_siting/analysis/factors.py`
- Test: `tests/analysis/test_competition_pools.py`

- [ ] **Step 1: 寫失敗測試**

```python
from clinic_siting.analysis.factors import (
    ALL_FACTORS, build_factors, competition_pool_score)


def test_competition_aesthetic_removed():
    assert "competition_aesthetic" not in ALL_FACTORS
    assert "competition" in ALL_FACTORS
    assert len(ALL_FACTORS) == 13


def test_single_pool_matches_direct():
    # 單池：分數等同該池 count 的競爭分
    raw = {"population": 100000, "competition_pools": [{"count": 10, "weighted": 10}]}
    f = build_factors(raw)
    assert f["competition"].source == "real"
    assert f["competition"].score == competition_pool_score(100000, 10)


def test_multi_pool_takes_min():
    # 雙池：取最嚴格（最低分）。醫美池家數多 → 分數低 → 勝出
    raw = {"population": 100000, "competition_pools": [
        {"count": 3, "weighted": 3}, {"count": 30, "weighted": 30}]}
    f = build_factors(raw)
    expected = min(competition_pool_score(100000, 3),
                   competition_pool_score(100000, 30))
    assert f["competition"].score == expected


def test_no_pools_missing():
    f = build_factors({"population": 100000})
    assert f["competition"].source == "missing"
    assert f["competition"].score == 50.0
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/analysis/test_competition_pools.py -v`
Expected: FAIL（`competition_pool_score` 不存在、`competition_aesthetic` 仍在）

- [ ] **Step 3: 實作**

在 `factors.py`：

1. `ALL_FACTORS` 移除 `"competition_aesthetic"`（剩 13 個）。
2. 將現有 `_competition_score` 對外命名 `competition_pool_score`（保留舊私有名為別名以免其他引用斷）：

```python
def competition_pool_score(population, count) -> float:
    """單一競爭池：需求 vs 供給。需求>供給→群聚加分；過密才扣分。"""
    demand = population * VISIT_RATE
    if count == 0:
        return NO_COMPETITION_SCORE
    demand_per_clinic = demand / count
    return minmax_score(demand_per_clinic, DEMAND_PER_CLINIC_LO, DEMAND_PER_CLINIC_HI)


_competition_score = competition_pool_score  # 舊名別名
```

3. 在 `build_factors` 中，把原本 `competition` 與 `competition_aesthetic` 兩段，換成單一「多池取 min」：

```python
    pools = raw.get("competition_pools")
    if pools:
        pop = raw.get("population", 0)
        scores = []
        for pl in pools:
            eff = pl.get("weighted")
            if eff is None:
                eff = pl.get("count", 0)
            scores.append(competition_pool_score(pop, eff))
        out["competition"] = FactorResult(min(scores), "real")
    else:
        out["competition"] = FactorResult(NEUTRAL, "missing")
```

移除原 `competition_aesthetic` 的整段 build 邏輯。

4. `factor_explanation` 中移除 `competition_aesthetic` 分支；改寫 `competition` 分支讀 `competition_pools`：

```python
    if name == "competition":
        pools = raw.get("competition_pools")
        if not pools:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        pop = raw.get("population") or 0
        demand = pop * VISIT_RATE
        parts = []
        for pl in pools:
            eff = pl.get("weighted", pl.get("count", 0))
            per = demand / eff if eff else 0.0
            tag = f"{pl.get('pool', '同業')}池 {pl.get('count', 0)} 家（每家 {per:,.0f}）"
            parts.append(tag)
        return {
            "raw": "｜".join(parts) + f"｜月需求估 {demand:,.0f} 人次",
            "basis": (f"每池需求/供給映射 {DEMAND_PER_CLINIC_LO:.0f}–"
                      f"{DEMAND_PER_CLINIC_HI:.0f} → 0–100，多池取最嚴格（最低分）"),
        }
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/analysis/test_competition_pools.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/analysis/factors.py tests/analysis/test_competition_pools.py
git commit -m "feat: 競爭因子改多池取最嚴格，移除寫死 competition_aesthetic"
```

---

## Task 4: 競爭者/錨點來源 adapter

**Files:**
- Create: `src/clinic_siting/data_sources/competitors.py`
- Test: `tests/data_sources/test_competitors.py`

adapter 把 profile 的競爭/錨點宣告轉成「已算好距離的點位清單」。實際網路抓取沿用既有 `google_places` / `osm_poi` 模組；本 adapter 只負責「依 source 分派 + classify 過濾 + 分池」，並以注入 fetch 函式讓測試離線。

- [ ] **Step 1: 寫失敗測試**

```python
from clinic_siting.data_sources.competitors import (
    scan_pool, scan_anchors)


def _fake_google(types, keywords):
    # 回傳固定點位（帶 name/types），忽略 types/keywords
    return [
        {"lat": 25.0, "lon": 121.0, "name": "康健診所", "types": ["medical_clinic"]},
        {"lat": 25.001, "lon": 121.0, "name": "美麗醫美診所", "types": ["skin_care_clinic"]},
        {"lat": 25.002, "lon": 121.0, "name": "王小明牙醫", "types": ["dentist"]},
    ]


def _fake_osm(tags):
    return [{"lat": 25.0, "lon": 121.0, "name": "阿宗麵線", "types": []}]


CENTER = (25.0, 121.0)


def test_google_pool_classify_western():
    pool = {"source": "google_places", "pool": "western",
            "types": ["medical_clinic"], "classify": "western"}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    names = {p["name"] for p in pts}
    assert "康健診所" in names           # western
    assert "美麗醫美診所" not in names   # aesthetic 被濾掉
    assert "王小明牙醫" not in names     # dental 被濾掉


def test_google_pool_classify_aesthetic():
    pool = {"source": "google_places", "pool": "aesthetic",
            "types": ["skin_care_clinic"], "classify": "aesthetic"}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert {p["name"] for p in pts} == {"美麗醫美診所"}


def test_osm_pool_no_classify_keeps_all():
    pool = {"source": "osm", "tags": {"amenity": "restaurant"}}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert {p["name"] for p in pts} == {"阿宗麵線"}


def test_points_have_distance():
    pool = {"source": "osm", "tags": {"amenity": "restaurant"}}
    pts = scan_pool(CENTER, pool, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert "dist_km" in pts[0]


def test_scan_anchors_osm():
    spec = {"source": "osm", "tags": {"shop": "convenience"}}
    pts = scan_anchors(CENTER, spec, google_fetch=_fake_google, osm_fetch=_fake_osm)
    assert pts and "dist_km" in pts[0]
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/data_sources/test_competitors.py -v`
Expected: FAIL（模組不存在）

- [ ] **Step 3: 實作**

```python
from __future__ import annotations

from clinic_siting.analysis.aggregate import DRIVE_KM, WALK_KM
from clinic_siting.analysis.competition import classify_place
from clinic_siting.geo.distance import haversine_km
from clinic_siting.geo.grid import tile_centers
from clinic_siting.data_sources import env, google_places, osm_poi

_COMP_STEP_KM = 1.2
_COMP_SUB_M = 900


def _default_google_fetch(center, types, keywords):
    """網格掃描 3km 內 google places；回傳點位 dict 清單（含 name/types）。"""
    key = env.get_key("GOOGLE_MAPS_API_KEY")
    if not key:
        return []
    seen: dict = {}
    for la, lo in tile_centers(center, DRIVE_KM, _COMP_STEP_KM):
        try:
            resp = google_places.fetch_search_nearby(
                types, la, lo, _COMP_SUB_M, key)
        except Exception:
            continue
        for p in google_places.parse_places(resp):
            if p.lat and p.lon:
                seen[(round(p.lat, 5), round(p.lon, 5))] = {
                    "lat": p.lat, "lon": p.lon, "name": p.name,
                    "types": list(p.types or []),
                    "address": getattr(p, "address", ""),
                    "rating": getattr(p, "rating", None),
                    "rating_count": getattr(p, "rating_count", None),
                }
    return list(seen.values())


def _default_osm_fetch(center, tags):
    """單一 tag 查 Overpass；回傳點位 dict 清單。"""
    (k, v), = tags.items()
    q = osm_poi.build_query(k, v, center[0], center[1], int(DRIVE_KM * 1000))
    out = []
    for o in osm_poi.parse_overpass(osm_poi.fetch_overpass(q)):
        if o.lat and o.lon:
            out.append({"lat": o.lat, "lon": o.lon,
                        "name": getattr(o, "name", ""), "types": []})
    return out


def _annotate(center, pts):
    for p in pts:
        p["dist_km"] = round(
            haversine_km(center[0], center[1], p["lat"], p["lon"]), 2)
    return [p for p in pts if p["dist_km"] <= DRIVE_KM]


def scan_pool(center, pool, google_fetch=None, osm_fetch=None):
    """掃一個競爭池 → 已標距離、（若有 classify）已過濾的點位清單。"""
    source = pool["source"]
    if source == "google_places":
        raw = (google_fetch or (lambda t, k: _default_google_fetch(center, t, k)))(
            pool.get("types", []), pool.get("keywords", []))
    elif source == "osm":
        raw = (osm_fetch or (lambda tg: _default_osm_fetch(center, tg)))(
            pool.get("tags", {}))
    else:
        raise ValueError(f"未知競爭來源: {source}")

    classify = pool.get("classify")
    if classify:
        raw = [p for p in raw
               if classify_place(p.get("name", ""), p.get("types")) == classify]
    return _annotate(center, raw)


def scan_anchors(center, spec, google_fetch=None, osm_fetch=None):
    """掃互補錨點 → 已標距離的點位清單。"""
    if not spec:
        return []
    source = spec["source"]
    if source == "google_places":
        raw = (google_fetch or (lambda t, k: _default_google_fetch(center, t, k)))(
            spec.get("types", []), spec.get("keywords", []))
    elif source == "osm":
        raw = (osm_fetch or (lambda tg: _default_osm_fetch(center, tg)))(
            spec.get("tags", {}))
    else:
        raise ValueError(f"未知錨點來源: {source}")
    return _annotate(center, raw)
```

註：測試注入的 `google_fetch(types, keywords)` / `osm_fetch(tags)` 簽名與內部 lambda 對齊。

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/data_sources/test_competitors.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/data_sources/competitors.py tests/data_sources/test_competitors.py
git commit -m "feat: 競爭者/錨點來源 adapter（google_places / osm，可注入測試）"
```

---

## Task 5: pipeline 拆 collect_location / collect_industry

**Files:**
- Modify: `src/clinic_siting/pipeline.py`
- Test: `tests/test_pipeline.py`（新增測試，保留既有）

- [ ] **Step 1: 寫失敗測試**

```python
from clinic_siting.pipeline import collect_industry
from clinic_siting.scoring.config import IndustryProfile


def test_collect_industry_builds_pools(monkeypatch):
    import clinic_siting.pipeline as pl

    def fake_scan_pool(center, pool, **kw):
        return [{"lat": 25.0, "lon": 121.0, "name": "x", "dist_km": 0.5}]

    def fake_scan_anchors(center, spec, **kw):
        return [{"lat": 25.0, "lon": 121.0, "name": "a", "dist_km": 0.3}]

    monkeypatch.setattr(pl, "scan_pool", fake_scan_pool)
    monkeypatch.setattr(pl, "scan_anchors", fake_scan_anchors)

    prof = IndustryProfile(
        id="bubble_tea", group="food", label="手搖飲",
        competitors=[{"source": "osm", "tags": {"amenity": "cafe"}}],
        anchors={"source": "osm", "tags": {"amenity": "school"}},
        weights={},
    )
    raw, geo = collect_industry((25.0, 121.0), prof)
    assert raw["competition_pools"][0]["count"] == 1
    assert raw["anchor_count"] == 1
    assert geo["competitors"] and geo["anchors"]
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_pipeline.py::test_collect_industry_builds_pools -v`
Expected: FAIL（`collect_industry` 不存在）

- [ ] **Step 3: 實作**

在 `pipeline.py`：

1. 頂部 import 新增：`from clinic_siting.data_sources.competitors import scan_pool, scan_anchors`；並 `from clinic_siting.analysis.aggregate import weighted_count_within, count_within`（已在）。
2. 刪除舊的 `_scan_competitors`、`_COMP_TYPES`、`_COMP_STEP_KM`、`_COMP_SUB_M`（移至 competitors.py）。
3. 新增 `collect_industry`：

```python
def collect_industry(center, profile):
    """依 profile 掃競爭池與錨點；回傳 (raw, geo)。"""
    raw: dict = {}
    geo: dict = {}
    pools_out = []
    competitors_geo = []
    for pool in profile.competitors:
        pts = scan_pool(center, pool)
        cnt = count_within(center, pts, DRIVE_KM)
        wt = round(weighted_count_within(center, pts, DRIVE_KM), 2)
        pools_out.append({"pool": pool.get("pool", "同業"),
                          "count": cnt, "weighted": wt})
        competitors_geo.extend(pts)
    if pools_out:
        raw["competition_pools"] = pools_out
        geo["competitors"] = competitors_geo

    anchors = scan_anchors(center, profile.anchors)
    if anchors:
        raw["anchor_count"] = count_within(center, anchors, DRIVE_KM)
        raw["anchor_weighted"] = round(
            weighted_count_within(center, anchors, DRIVE_KM), 2)
        geo["anchors"] = anchors
    return raw, geo
```

4. 從 `collect_live` 移除競爭掃描與 pharmacy/hospital 錨點掃描兩段（其餘地點因子保留），並將函式改名 `collect_location`。保留舊名別名一行 `collect_live = collect_location` 供既有測試（若有）暫時相容，Task 6 一併清。

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS（含新測試）

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/pipeline.py tests/test_pipeline.py
git commit -m "feat: 收集層拆 collect_location / collect_industry，競爭掃描移入 adapter"
```

---

## Task 6: run_pipeline 迴圈行業 + 新快照 schema

**Files:**
- Modify: `src/clinic_siting/pipeline.py`, `src/clinic_siting/snapshot.py`
- Test: `tests/test_pipeline.py`, `tests/test_snapshot.py`

- [ ] **Step 1: 寫失敗測試（離線 run_pipeline 產新 schema）**

```python
from pathlib import Path
from clinic_siting.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
CONFIG = ROOT / "config" / "industries.yaml"


def test_run_pipeline_offline_new_schema(tmp_path):
    hist = tmp_path / "h.jsonl"
    snap = run_pipeline(REF, hist, CONFIG, live=False)
    assert "location" in snap and "industries" in snap
    assert "factors" in snap["location"]
    fam = snap["industries"]["family_medicine"]
    assert fam["group"] == "medical"
    assert "score" in fam and isinstance(fam["score"], float)
    # 完整 13 因子都在
    assert "competition" in fam["factors"]
    assert "population_density" in fam["factors"]
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_pipeline.py::test_run_pipeline_offline_new_schema -v`
Expected: FAIL（run_pipeline 仍為舊 schema / 用 specialties）

- [ ] **Step 3: 實作 run_pipeline**

改寫 `run_pipeline`：

```python
from clinic_siting.scoring.config import load_industry_config
from clinic_siting.scoring.engine import score_industry


def run_pipeline(reference_dir, history_path, config_path,
                 live=False, center=geocode.SITE_LATLON, site_dir=None):
    raw = collect_offline(reference_dir)
    location_geo: dict = {}
    if live:
        loc_raw, location_geo = collect_location(center)
        raw.update(loc_raw)
        if "fia_business_count" in raw and "fia_business_total" in raw:
            ratio = fia_business.business_ratio(
                raw["fia_business_count"], raw["fia_business_total"],
                raw.get("population", 0), NATIONAL_POP)
            if ratio is not None:
                raw["business_ratio"] = round(ratio, 3)

    config = load_industry_config(config_path)
    last = load_last_snapshot(history_path)

    # 地點因子（全行業共用；此處先建一次供顯示）
    loc_factors = build_factors(raw)  # competition/anchors 此時為 missing
    loc_factors = fill_degraded_location(loc_factors, last)
    location = {
        "factors": {n: {"score": r.score, "source": r.source}
                    for n, r in loc_factors.items()
                    if n not in ("competition", "complementary_anchors")},
        "raw": raw,
    }

    industries: dict = {}
    for iid, prof in config.industries.items():
        ind_raw = dict(raw)
        ind_geo = {}
        if live:
            more_raw, ind_geo = collect_industry(center, prof)
            ind_raw.update(more_raw)
        factors = build_factors(ind_raw)
        factors = fill_degraded_industry(factors, last, iid)
        score = score_industry(factor_scores(factors), prof.weights)
        industries[iid] = {
            "group": prof.group,
            "label": prof.label,
            "score": round(score.score, 2),
            "factors": {n: {"score": r.score, "source": r.source}
                        for n, r in factors.items()},
            "raw": {k: ind_raw[k] for k in
                    ("competition_pools", "anchor_count", "anchor_weighted")
                    if k in ind_raw},
            "geo": ind_geo,
        }

    snapshot = {
        "date": date.today().isoformat(),
        "location": location,
        "industries": industries,
    }
    append_snapshot(history_path, snapshot)
    if site_dir is not None:
        from clinic_siting.site_export import build_site
        build_site(history_path, site_dir, config)
    return snapshot
```

新增 `score_industry` 於 `engine.py`：

```python
def score_industry(normalized_factors, weights):
    return score_specialty(normalized_factors, weights)
```

（`score_specialty` 邏輯不變；`score_all_specialties` 可保留至 Task 9。）

- [ ] **Step 4: snapshot 降級改為 per-industry**

在 `snapshot.py` 新增兩個 helper（`fill_degraded` 保留給舊格式）：

```python
def fill_degraded_location(factors, last):
    if not last:
        return factors
    prev = last.get("location", {}).get("factors", {})
    return _fill_from(factors, prev)


def fill_degraded_industry(factors, last, industry_id):
    if not last:
        return factors
    prev = (last.get("industries", {}).get(industry_id, {}).get("factors", {}))
    return _fill_from(factors, prev)


def _fill_from(factors, prev):
    for name, result in factors.items():
        if result.source != "missing":
            continue
        p = prev.get(name)
        if p and p.get("source") in _REUSABLE:
            factors[name] = FactorResult(p["score"], "degraded")
    return factors
```

`pipeline.py` import 這兩個 helper。

- [ ] **Step 5: 更新 runner/cli 指向 industries.yaml**

`runner.py`：`CONFIG_PATH = _ROOT / "config" / "industries.yaml"`；`main()` 印 `snap["industries"]` 分數：

```python
def main():
    snap = run_refresh()
    rows = [(iid, d["score"]) for iid, d in snap["industries"].items()]
    for iid, score in sorted(rows, key=lambda x: -x[1]):
        print(f"{iid:20s} {score:5.1f}")
```

`cli.py`：`CONFIG_PATH` 指向 `industries.yaml`；`load_specialty_config`→`load_industry_config`；`SAMPLE_FACTORS` 移除 `competition_aesthetic` 鍵；`run_demo` 用 `score_industry` 逐一計分 `config.industries`。

- [ ] **Step 6: 執行確認通過**

Run: `pytest tests/test_pipeline.py tests/test_snapshot.py tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/clinic_siting/pipeline.py src/clinic_siting/snapshot.py src/clinic_siting/scoring/engine.py src/clinic_siting/runner.py src/clinic_siting/cli.py tests/
git commit -m "feat: run_pipeline 迴圈行業產出 location+industries 兩層快照"
```

---

## Task 7: site_export 讀 industries 兩層

**Files:**
- Modify: `src/clinic_siting/site_export.py`
- Test: `tests/test_site_export.py`

- [ ] **Step 1: 寫失敗測試**

```python
from clinic_siting.site_export import build_payload
from clinic_siting.scoring.config import load_industry_config
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config" / "industries.yaml"


def _snap(date, fam_score):
    return {
        "date": date,
        "location": {"factors": {
            "population_density": {"score": 75.0, "source": "real"}},
            "raw": {"population": 180000}},
        "industries": {
            "family_medicine": {"group": "medical", "label": "家醫科",
                "score": fam_score,
                "factors": {"population_density": {"score": 75.0, "source": "real"},
                            "competition": {"score": 60.0, "source": "real"}},
                "raw": {}, "geo": {}},
            "bubble_tea": {"group": "food", "label": "手搖飲",
                "score": 55.0,
                "factors": {"population_density": {"score": 75.0, "source": "real"},
                            "competition": {"score": 50.0, "source": "real"}},
                "raw": {}, "geo": {}},
        },
    }


def test_payload_groups_industries():
    cfg = load_industry_config(CONFIG)
    payload = build_payload([_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], cfg)
    assert "groups" in payload
    assert "medical" in payload["groups"]
    assert "family_medicine" in payload["groups"]["medical"]["industries"]


def test_payload_trend_per_industry():
    cfg = load_industry_config(CONFIG)
    payload = build_payload([_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], cfg)
    trend = payload["groups"]["medical"]["industries"]["family_medicine"]["trend"]
    assert trend == [70.0, 72.0]
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_site_export.py -v`
Expected: FAIL（build_payload 仍用 specialties 結構）

- [ ] **Step 3: 實作**

改寫 `site_export.py` 核心函式。`build_payload` 輸出：

```python
def build_payload(snapshots, config=None):
    latest = snapshots[-1] if snapshots else {}
    dates = [s["date"] for s in snapshots]
    industries_meta = latest.get("industries", {})

    groups: dict[str, dict] = {}
    for iid, meta in industries_meta.items():
        g = meta["group"]
        trend = [s.get("industries", {}).get(iid, {}).get("score") for s in snapshots]
        entry = {
            "label": meta["label"],
            "score": meta["score"],
            "trend": trend,
            "factors": _industry_factor_table(snapshots, iid),
            "breakdown": _industry_breakdown(meta, config, iid) if config else None,
            "geo": meta.get("geo", {}),
        }
        groups.setdefault(g, {"industries": {}})["industries"][iid] = entry

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": {"address": geocode.SITE_ADDRESS,
                 "latlon": list(geocode.SITE_LATLON)},
        "dates": dates,
        "location_factors": _location_factor_table(snapshots),
        "groups": groups,
    }
```

`_industry_factor_table(snapshots, iid)`：仿現有 `latest_factor_table`，但因子來源改讀 `s["industries"][iid]["factors"]`，raw 合併 `location.raw` 與該 industry `raw`，走 `factor_explanation`，並計算與上一筆同 industry 的 delta。`_location_factor_table`：對 11 個地點因子讀 `location.factors` + `location.raw`。`_industry_breakdown(meta, config, iid)`：用 `config.industries[iid].weights` 對 13 因子算貢獻（仿現有 `specialty_breakdowns` 單筆版）。

`build_site` 中 geo.json 改為輸出「所有行業 geo 的合集，鍵為 industry id」：

```python
    geo = {iid: d.get("geo", {})
           for iid, d in (snapshots[-1].get("industries", {}) if snapshots else {}).items()}
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_site_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clinic_siting/site_export.py tests/test_site_export.py
git commit -m "feat: site_export 依 group/industry 分組輸出 history.json 與分行業 geo"
```

---

## Task 8: 前端行業組切換

**Files:**
- Modify: `site/index.html`, `site/app.js`

- [ ] **Step 1: 讀現有前端結構**

Run: `sed -n '1,200p' site/app.js` 與 `sed -n '1,120p' site/index.html`，記下 DOM 容器 id 與 Leaflet 圖層建立方式（沿用其樣式/顏色）。

- [ ] **Step 2: 加行業組 + 行業選擇 UI**

在 `index.html` 排名區塊上方加兩層下拉/分頁：`<select id="groupSelect">`（醫療/餐飲/健身/教育/服務）與 `<div id="industryTabs">`（該組行業）。沿用既有 style.css 樣式類別。

- [ ] **Step 3: app.js 依新 payload 渲染**

改資料讀取為新結構：`data.groups[group].industries[iid]`。切換行業時更新:
- 分數/趨勢圖 → 該 industry 的 `trend` 對 `data.dates`。
- 因子表 → `data.location_factors`（共用區塊，標「地點因子」）＋ 該 industry `factors`（標「行業因子」）。
- 加權拆解 → 該 industry `breakdown`。
- 地圖圖層 → `geo.json[iid]`，圖層 `competitors`（原 clinics 顏色）＋ `anchors`；移除寫死的 `clinics`/`aesthetic` 圖層名，改為通用 `competitors`。

保留既有 what-if 權重滑桿：作用對象改為當前選中的 industry。

- [ ] **Step 4: 手動驗證（preview）**

用 preview 工具起本地站，切換不同行業組，確認排名/趨勢/因子表/地圖圖層都隨行業更新、無 console error。（依 preview_* workflow：start → snapshot → console_logs → screenshot。）

- [ ] **Step 5: Commit**

```bash
git add site/index.html site/app.js site/style.css
git commit -m "feat: 前端加行業組切換，地圖圖層通用化為 competitors/anchors"
```

---

## Task 9: 套件更名 clinic_siting → site_siting（獨立、最後）

此任務純機械更名，與功能無關；獨立成一 commit，若造成問題可單獨回退。

**Files:**
- Rename: `src/clinic_siting/` → `src/site_siting/`；全域 import 字串替換；`pytest.ini`、`deploy/`、`.github/workflows/` 內引用。

- [ ] **Step 1: 目錄更名**

```bash
git mv src/clinic_siting src/site_siting
```

- [ ] **Step 2: 全域替換 import 字串**

```bash
grep -rl "clinic_siting" src tests deploy .github pytest.ini | xargs sed -i '' 's/clinic_siting/site_siting/g'
```

- [ ] **Step 3: 全測試通過**

Run: `pytest -q`
Expected: PASS（全綠）

- [ ] **Step 4: 更名設定/文件引用檢查**

Run: `grep -rn "specialties.yaml\|clinic_siting" src tests deploy .github`
Expected: 無殘留（`specialties.yaml` 已於 Task 6 改指 `industries.yaml`；如有殘留一併修正）。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: 套件更名 clinic_siting → site_siting（泛化為通用選址）"
```

---

## Task 10: 回歸驗證 — 醫療類分數不變

**Files:**
- Test: `tests/test_regression_medical.py`

- [ ] **Step 1: 寫回歸測試**

以固定 raw（含 `competition_pools` 單池 western）分別用「舊 specialties.yaml 權重 + 舊單池 competition」與「新 industries.yaml medical 權重」計分，斷言 5 個醫療 profile 分數一致（容差 1e-6）。實作時以 `config/specialties.yaml` 的權重為期望基準，逐一比對 `industries.yaml` medical 對映。

```python
from pathlib import Path
from site_siting.scoring.config import load_industry_config, load_specialty_config
from site_siting.scoring.engine import score_industry, score_specialty

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "config" / "specialties.yaml"      # 若已刪除，改用內嵌期望權重
NEW = ROOT / "config" / "industries.yaml"

FIXED = {  # 13 因子（新集合）固定分數
    "population_density": 75.0, "age_gender": 70.0, "day_night_gap": 60.0,
    "school_proximity": 65.0, "purchasing_power": 80.0, "business_density": 65.0,
    "land_use_mix": 60.0, "competition": 55.0, "complementary_anchors": 60.0,
    "convenience_density": 85.0, "accessibility": 70.0, "redevelopment_stage": 90.0,
    "visibility": 50.0,
}

MEDICAL = ["family_medicine", "functional_medicine", "weight_loss",
           "psychiatry", "aesthetics"]


def test_medical_weights_preserved():
    new = load_industry_config(NEW)
    old = load_specialty_config(OLD)
    for name in MEDICAL:
        w_old = dict(old.specialties[name])
        # 舊 aesthetics 的 competition_aesthetic 對映新第二池；此處僅比對非競爭因子權重一致
        for f, v in new.industries[name].weights.items():
            if f == "competition":
                continue
            assert w_old[f] == v, f"{name}.{f} 權重變動"
```

註：`competition` 因舊為雙因子、新為多池，語意改變不做等值斷言，僅保證其餘 12 因子權重零漂移。若 Task 9 已刪 `specialties.yaml`，改為內嵌舊權重常數比對。

- [ ] **Step 2: 執行確認通過**

Run: `pytest tests/test_regression_medical.py -v`
Expected: PASS

- [ ] **Step 3: 全套件回歸**

Run: `pytest -q`
Expected: PASS（全綠）

- [ ] **Step 4: Commit**

```bash
git add tests/test_regression_medical.py
git commit -m "test: 醫療類非競爭因子權重零漂移回歸測試"
```

---

## 完成後

- 執行一次離線刷新產生新 schema 快照供前端檢視：`python -m site_siting.runner`（或既有入口），或 `run_refresh(live=False)`。
- 舊 `config/specialties.yaml`：Task 9 後若確認無引用可刪除（獨立 commit）。
- 舊 `history.jsonl`：屬舊 schema，首次新刷新後並存；如需前端相容舊資料，`site_export` 已只讀新結構，舊筆會被忽略（可接受，屬歷史資料）。
