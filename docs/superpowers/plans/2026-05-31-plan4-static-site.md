# Plan 4 — 靜態 HTML 趨勢站 Implementation Plan

> **For agentic workers:** 用 TDD 逐步實作，純函式先測，前端用 CDN 零建置。

**Goal:** 把 `history.jsonl` 快照轉成前端可讀的 `history.json` + `geo.json`，並產出純靜態 `site/`（Chart.js 雷達／趨勢／因子長條圖 + Leaflet 地圖），無建置步驟、可直接開或託管。

**Architecture:**
- `site_export.py`：純函式把快照序列轉成前端資料結構（series/radar/factors），`build_site()` 寫出 `site/data/history.json`；最新一筆的地理點位寫 `site/data/geo.json`。
- `pipeline.py`：`collect_live` 改為同時回傳計數與地理點位；`run_pipeline` 把點位存進快照 `geo` 欄位，並於 append 後可選擇呼叫 `build_site`。
- `site/index.html` + `app.js` + `style.css`：CDN 載入 Chart.js + Leaflet，fetch 兩個 JSON 後繪圖。

**Tech Stack:** Python 3.9（`from __future__ import annotations`）、pytest、stdlib json；前端純 HTML/JS + Chart.js 4 + Leaflet 1.9（CDN）。

---

## Task 1: site_export.py — 快照 → 前端 JSON（純函式）

**Files:**
- Create: `src/clinic_siting/site_export.py`
- Test: `tests/test_site_export.py`

- `trend_series(snapshots) -> {"dates": [...], "specialties": {name: [score,...]}}`：跨快照折線資料。
- `latest_radar(snapshots) -> {"labels": [5 科別], "scores": [最新分數,...]}`。
- `latest_factor_bars(snapshots) -> [{"factor","score","source"},...]`（依 ALL_FACTORS 順序）。
- `build_payload(snapshots) -> {"generated","meta","trend","radar","factors"}`（meta 含 address/latlon，geo 不含於此）。
- `build_site(history_path, site_dir)`：讀 jsonl → 寫 `site_dir/data/history.json`（payload）與 `site_dir/data/geo.json`（最新快照 `geo` 或 `{}`）。
- 測試：合成 2–3 筆快照 → 驗證 series 對齊日期、radar 取最後一筆、factors 順序、build_site 落檔且為合法 JSON。

## Task 2: pipeline 擷取地理點位 + 串接 build_site

**Files:**
- Modify: `src/clinic_siting/pipeline.py`
- Test: `tests/test_pipeline.py`（補測）

- `collect_live(center) -> (raw, geo)`：一次抓點，`raw` 為計數、`geo` 為 `{clinics,anchors,convenience,transit: [{lat,lon,name}]}`。
- `run_pipeline(..., site_dir=None)`：離線時 `geo={}`；live 時填入；snapshot 加 `geo` 欄位；若給 `site_dir` 則 append 後呼叫 `build_site`。
- 測試（離線決定性）：snapshot 含 `geo`（離線為 `{}`）；給 `site_dir` 時 `site/data/history.json` 生成且含 5 科別 trend。

## Task 3: 靜態前端 site/

**Files:**
- Create: `site/index.html`, `site/app.js`, `site/style.css`
- Create: `site/data/.gitkeep`

- `index.html`：CDN 載 Chart.js + Leaflet，四區塊（雷達／趨勢／因子長條／地圖）。
- `app.js`：`fetch('data/history.json')` 與 `data/geo.json`；畫三圖；Leaflet 標候選點 + 雙半徑圈（1km/3km）+ 競爭點 marker；缺 geo 時隱藏地圖區塊不報錯。
- `style.css`：簡潔響應式版面。
- 驗證：以離線 + live 各跑一次 build_site，產出 JSON 後人工確認 `index.html` 結構與資料鍵對齊（用 Read／python 檢查 JSON schema；不需瀏覽器）。

## Task 4: 全套件 + 端到端產站 + commit

- `pytest -q` 全綠。
- live `run_pipeline(..., site_dir='site', live=True)` 實跑：確認 `site/data/history.json`、`geo.json` 內容正確、競爭點有座標。
- `.gitignore`：`site/data/*.json` 不入版控（生成物），保留 `site/` 程式碼。
- Commit。
