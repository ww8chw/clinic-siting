# 多行業選址系統設計（診所選址泛化）

- 日期：2026-07-01
- 狀態：已核准設計，待實作計畫
- 前身規格：`docs/superpowers/specs/2026-05-30-clinic-location-assessment-design.md`

## 目標

把現有「診所選址評估系統」（`clinic_siting`）泛化為**通用多行業選址系統**，在**同一個固定候選地點**（桃園龜山樂善里）上，評估診所以外的其他店面型行業（餐飲、手搖飲、健身房、補習班、咖啡、美容美髮…）。

- **使用模式**：固定地點 + 多行業（維持現有單一地點每月追蹤模式，把「科別 specialty」換成「行業 industry profile」）。
- **行業範圍**：策展式清單（curated）。每個行業一份設定檔，內含專家調校的因子權重與競爭者定義。新增行業＝加一份設定檔，不改核心程式。
- **不變的核心價值**：每個行業有專家調校過的權重；以及既有 14 因子的計分邏輯與 0–100 校準。

### 非目標（YAGNI）

- 不做任意地點輸入 / 即時任意地址評估（未來若要再開）。
- 不做多候選地點 PK 排名。
- 不做完全開放的自由行業輸入。
- 不動固定地點的地理／人口常數（龜山區、樂善里、SITE_LATLON）。

## 核心洞察

現有 14 因子中，只有 **3 樣真正因行業而異**：競爭者、互補錨點、因子權重。其餘 11 個都是**地點屬性**，與販售的商品無關：

| 類型 | 因子 | 是否因行業而異 |
|------|------|----------------|
| 地點因子（全行業共用，每次 refresh 算一次） | population_density, age_gender, day_night_gap, school_proximity, purchasing_power, business_density, land_use_mix, convenience_density, accessibility, redevelopment_stage, visibility | 否 |
| 行業因子（每個行業各自掃描） | competition（含多池）, complementary_anchors | 是 |
| 權重 | 全部 14 因子的 0–5 權重 | 是 |

因此固定地點下：地點因子每月算一次 → 各行業只需「額外掃自己的競爭者/錨點池 + 套自己的權重計分」，共用地點因子、避免重複 API 呼叫。

## 採用方案

**方案 A：設定驅動 + 可插拔競爭者來源。** 拆掉三處診所耦合（命名/概念、競爭者資料源寫死、因子語意寫死），把它們全部變成設定驅動。診所科別收編為 `medical` group 下的 profiles，行為不變。

（已排除：方案 B 最小 shim — 留下耦合與技術債；方案 C 完整 plugin registry — 對「因子固定、僅權重與來源不同」的需求過度設計。）

## 概念模型

行業設定檔（industry profile）依 group 歸類：

```
group: medical    → family_medicine, functional_medicine, weight_loss, psychiatry, aesthetics（收編現有）
group: food        → restaurant, bubble_tea, cafe
group: fitness     → gym
group: education   → cram_school
group: service     → hair_beauty
```

每個 profile 宣告：**競爭者池定義、互補錨點定義、14 因子權重**。其餘計分邏輯全行業共用。

## 設定檔結構（`config/industries.yaml`，取代 `specialties.yaml`）

沿用現有 `weight_levels`（最高/高/中/低/無 → 5/4/3/2/0）、`factors`、`negative_factors` 區塊。每個 profile 擴充為：

```yaml
industries:
  bubble_tea:
    group: food
    label: 手搖飲
    competitors:
      - source: google_places          # google_places | osm
        types: [cafe]
        keywords: [手搖, 茶飲, 五十嵐, 清心, 迷客夏]   # searchText 補 type 抓不到者
    anchors:
      source: osm
      tags: { amenity: school }          # 手搖互補＝學校/補習班/年輕人流
    weights:
      population_density: 中
      age_gender: 高
      # …其餘因子權重
```

- `competitors` 是**列表**，可宣告 1 個或多個競爭池（見「競爭因子建模」）。
- `anchors` 定義互補錨點來源（取代寫死的 `["pharmacy", "hospital"]`）。
- `weights` 即原本 profile 的因子權重表。
- `competition_aesthetic` 這個寫死因子名**移除**；醫美改用「多競爭池」表達。

醫療類收編範例（保住現況雙池行為）：

```yaml
  aesthetics:
    group: medical
    label: 醫美
    competitors:
      - source: google_places             # 現有網格掃描 + classify
        types: [doctor, medical_clinic, hospital]
        pool: western                     # 一般診所池
        classify: western
      - source: google_places
        types: [beauty_salon, spa, skin_care_clinic, nail_salon]
        pool: aesthetic                   # 醫美池
        classify: aesthetic
    anchors:
      source: google_places
      types: [pharmacy, hospital]
    weights:
      # 對映原 aesthetics 權重（competition 對應一般診所池、原 competition_aesthetic 對應醫美池）
```

## 資料收集重構

`collect_live()` 拆成兩層：

### `collect_location(center) -> (raw, geo)`
搬移現有 11 個地點因子的收集邏輯（人口、所得、年齡性別、晝夜、學校、超商、商業密度、土地使用、能見度、屋齡、可及性）。**移除**寫死的競爭者網格掃描與 pharmacy/hospital 錨點掃描。每次 refresh 呼叫一次。

### `collect_industry(center, profile) -> (raw, geo)`
依 profile 定義只做兩件事：
1. 掃描 `competitors` 各池 → 每池產出 `competition_count` / `competition_weighted`。
2. 掃描 `anchors` → `anchor_count` / `anchor_weighted`。

### 競爭者來源 adapter

一層分派器把 profile 的 `source` 對應到抓取實作：

| source | 實作 | 用途 |
|--------|------|------|
| `google_places` | 現有 `_scan_competitors` 網格掃描，改吃 profile 的 `types` + `keywords`；可選 `classify` + `pool` 分池 | 一般行業＋醫療類（醫療用 classify 分西醫/醫美池） |
| `osm` | Overpass tag 查詢（沿用 `osm_poi.build_query`） | 有明確 OSM tag 的行業 |

`classify_place` 從寫死西醫/醫美規則改為**吃 profile 宣告的 `classify` 規則**；醫療類沿用原西醫/醫美規則常數。

註：NHI 健保診所名冊（`nhi_clinics.py`）是既有的獨立資料源，用途為診所目錄，**不參與競爭計分**（競爭一律走 Google Places 網格掃描），本次不變更。

## 競爭因子建模（已核准）

- 移除寫死的 `competition_aesthetic` 因子名。
- 每個 profile 宣告 **1 個或多個競爭池**；每池各用現有 `_competition_score`（需求 vs 供給）算一個分數。
- profile 的 `competition` 因子分數 = **各池取最嚴格（最低分）**。
- 醫美 = 宣告一般診所池 + 醫美池兩池（等同現況雙池嚴格度）；手搖/餐飲等 = 單池。

`build_factors` 調整：`competition` 改為接受「池分數列表」取 min；`factor_explanation` 的 competition 說明改為列出各池家數與最終取值池。

## 前端變更（`site/`）

- 排名頁改為：**先選行業組（醫療／餐飲／健身／教育／服務）→ 顯示該組各 profile 的評分、趨勢、因子分解、地圖**。
- 地圖 `clinics` 圖層更名 `competitors`（通用語意）；`anchors` 圖層語意隨行業變（tooltip 文案取自 profile）。
- `site/data/history.json` 結構加一層 `industry` key：`{ industry_id: { scores, factors, geo, trend } }`。地點因子可放共用區塊避免重複。

## 更名對照

| 現況 | 變更後 |
|------|--------|
| 套件 `clinic_siting` | `site_siting` |
| `config/specialties.yaml` | `config/industries.yaml` |
| `load_specialty_config` | `load_industry_config` |
| `score_all_specialties` | `score_all_industries` |
| 因子 `competition_aesthetic` | 移除（改多競爭池） |
| geo 圖層 `clinics` | `competitors` |

固定地點常數（`INCOME_DISTRICT`、`POP_REGION`、`SITE_SITE_ID`、`SITE_VILLAGE`、`geocode.SITE_LATLON`）**不變**。

## 相容與遷移

- 既有 `history.jsonl` 快照：醫療類欄位對映到 `medical` group profiles；舊快照仍可讀（`fill_degraded` 沿用上次值邏輯不變）。
- 新快照 schema 以 `industry` 為頂層鍵；讀取端相容舊格式（無 `industry` 鍵時視為醫療類）。

## 測試策略

- 每個競爭者 adapter（google_places / osm / nhi_google）一組單元測試（餵假 API 回應驗證計數與分池）。
- profile 設定載入測試：驗證 `industries.yaml` 解析、權重對映、競爭池宣告。
- **回歸測試**：以固定 raw 輸入，驗證 `medical` group 五個 profile 的分數與重構前一致（確保收編零損壞）。
- 競爭多池取最嚴格的計分測試（單池 = 現況；雙池 = 取 min）。
- collect_location / collect_industry 拆分後，地點因子只算一次的驗證。

## 開放項目

無。設計已核准，競爭建模決策已拍板（多池取最嚴格）。
