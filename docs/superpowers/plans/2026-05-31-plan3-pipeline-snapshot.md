# Plan 3 — 整合管線 + 快照 Implementation Plan

> **For agentic workers:** 用 TDD 逐步實作，每步先寫測試再實作；fixture 一律用小樣本。

**Goal:** 串接 Plan 2 抓取器與本地參考資料，對單一店址做雙半徑彙總 → 算出 12 因子正規化分數 → 評分 → 寫入 `history.jsonl`，並對缺漏來源做優雅降級。

**Architecture:**
- `data_sources/reference.py`：解析本地 `data/reference/` 的所得、人口 CSV（純函式、fixture 測）。
- `analysis/aggregate.py`：雙半徑（步行 1km / 車程 3km）空間彙總點位 → 原始計數。
- `analysis/factors.py`：原始值 → 12 因子 0–100 分 + 每因子來源狀態（real/degraded/manual/missing）；含同科別競爭「需求 vs 供給」群聚/稀釋、互補錨點分類。
- `snapshot.py`：append/load `history.jsonl`，缺漏因子沿用上次快照值並標註。
- `pipeline.py`：orchestrator，以 collector 蒐集原始輸入（離線參考檔必有、線上抓取可降級），輸出一筆完整 snapshot。

**Tech Stack:** Python 3.9（所有新模組加 `from __future__ import annotations`）、pytest（`pythonpath=src`）、stdlib csv/json/datetime。

---

## 因子資料可得性對照（決定每因子 source 狀態）

| 因子 | 來源 | 狀態 |
|---|---|---|
| purchasing_power | 本地所得 CSV（村里中位數） | real |
| population_density | 本地人口 CSV（區級）+ 所得 CSV 村里戶數 | real |
| competition | NHI 診所（線上）+ Google 評分 | real（線上失敗→降級） |
| complementary_anchors | NHI 藥局/醫院 + OSM | real（失敗→降級） |
| convenience_density | OSM `shop=convenience`（線上） | real（失敗→降級） |
| land_use_mix | OSM `landuse`（線上） | real（失敗→降級） |
| accessibility | TDX 公車站 + Google Distance Matrix | real（失敗→降級） |
| business_density | OSM POI 計數代理 | degraded（無營業稅籍全量） |
| age_gender | （未下載單齡人口） | missing→neutral 50 |
| day_night_gap | SEGIS（需登入） | missing→neutral 50 |
| redevelopment_stage | （未下載實價/重劃區） | manual→neutral 50 |
| visibility | 使用者手動 | manual→neutral 50 |

降級規則：線上來源缺漏 → 先沿用上次 snapshot 該因子值（標 `degraded`）；無上次值 → neutral 50（標 `missing`）。手動因子預設 neutral 50（標 `manual`），未來由 Plan 4 介面覆寫。

---

## Task 1: reference.py — 本地參考 CSV 解析

**Files:**
- Create: `src/clinic_siting/data_sources/reference.py`
- Test: `tests/data_sources/test_reference.py`
- Fixtures: `tests/fixtures/income_guishan_sample.csv`, `tests/fixtures/population_taoyuan_sample.csv`

- 從真實檔擷取龜山區小樣本當 fixture。
- `parse_income_csv(text) -> dict[str, dict]`：village → {households, median, mean}（utf-8-sig，欄位：縣市別/村里/納稅單位(戶)/綜合所得總額/平均數/中位數）。
- `parse_population_csv(text) -> dict[str, dict]`：region(去「區」) → {population, households}（兩列性別加總）。
- `district_income_summary(income, district_prefix)`：回傳該區所有村里的 households 加總、戶中位所得的人口加權平均（代理消費力）。

## Task 2: aggregate.py — 雙半徑彙總

**Files:**
- Create: `src/clinic_siting/analysis/__init__.py`, `src/clinic_siting/analysis/aggregate.py`
- Test: `tests/analysis/test_aggregate.py`

- `WALK_KM=1.0`、`DRIVE_KM=3.0`。
- `count_within(center, points, radius_km) -> int`（用既有 `geo.radius.points_within_radius`）。
- `dual_radius_counts(center, points) -> dict`：`{"walk": n1, "drive": n2}`。
- `summarize_points(center, named_points) -> dict[str, {walk,drive}]`：對多組命名點位（clinics/pharmacies/convenience/transit…）一次算雙半徑計數。
- 合成點位測距離篩選正確（剛好在界內/界外）。

## Task 3: factors.py — 12 因子正規化

**Files:**
- Create: `src/clinic_siting/analysis/factors.py`
- Test: `tests/analysis/test_factors.py`

- 校準門檻為模組常數（以龜山量級設定 lo/hi），用既有 `scoring.normalize.minmax_score`。
- `FactorResult` = `{score: float, source: str}`；`build_factors(raw: dict) -> dict[str, FactorResult]`，含 12 因子。
- competition：先算 `demand = population * 就診率係數`、`supply = 同科別家數`；需求>供給 → 群聚加分、過密才扣分（非單純越多越差）。回傳 0–100（已處理負向語意）。
- complementary_anchors：藥局/醫院/健檢等家數加權求和 → 正規化。
- 缺漏 raw key → 該因子 neutral 50 + source 標記（missing/manual）。
- 測試：固定 raw → 重現分數；缺 key → 50/標記正確；competition 群聚情境分數高於過密情境。

## Task 4: snapshot.py — 歷史快照

**Files:**
- Create: `src/clinic_siting/snapshot.py`
- Test: `tests/test_snapshot.py`

- `append_snapshot(path, snapshot: dict)`：JSONL 追加一行（含 `date`、`scores`、`factors`、`raw`）。
- `load_last_snapshot(path) -> dict | None`：讀最後一行。
- `fill_degraded(factors, last) -> factors`：source==missing 且 last 有該因子真值 → 沿用並標 degraded。
- 測試用 `tmp_path`：append→load round-trip、fill_degraded 行為。

## Task 5: pipeline.py — orchestrator

**Files:**
- Create: `src/clinic_siting/pipeline.py`
- Test: `tests/test_pipeline.py`

- `collect_offline(reference_dir) -> raw`：只用本地參考檔 + 中性線上值（決定性，可測）。
- `collect_live(...)`：嘗試線上抓取，每來源 try/except 失敗則略過該 raw key（交給 factors/snapshot 降級）。
- `run_pipeline(reference_dir, history_path, config_path, live=False) -> snapshot`：collect → build_factors → fill_degraded(上次) → score_all_specialties → 組 snapshot → append。
- 測試（離線決定性）：跑兩次 → 兩筆一致分數；輸出含 5 科別分數與 12 因子；competition 為負向但分數合理。

## Task 6: 全套件 + 真實端到端冒煙 + commit

- `pytest -q` 全綠。
- 真實冒煙（有金鑰時）：`run_pipeline(..., live=True)` 實跑一次，印出 5 科別排名與各因子 source，人工確認線上來源確有連通、缺漏有正確降級。
- 確認 `.env`、大型 CSV 未進版控（`data/reference/*.csv` 可入版控，屬小型參考檔；fixtures 為樣本）。
- Commit。
