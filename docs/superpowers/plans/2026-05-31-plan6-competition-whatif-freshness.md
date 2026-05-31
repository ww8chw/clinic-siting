# Plan 6 — 競爭分流(方案A) + What-if 權重 + 資料新鮮度 + 本機定期更新

> **For agentic workers:** TDD 逐步實作；純函式先測（分類器、網格），編排層薄。

**Goal:** 修正周邊競爭嚴重低估（單次 Google 查詢 20 筆上限＋只查 doctor type → 漏掉近處 medical_clinic 與整批小診所），改用分區網格掃描＋名稱/型別分類，並把競爭拆成「西醫一般診所」與「醫美/美容」兩池按科別餵分（方案A）；前端加 what-if 權重滑桿與資料新鮮度徽章；資料更新改由本機 launchd 月度刷新（高品質金鑰）後 push 觸發 Pages 部署，停用雲端 degraded 排程。

**根因（已實測確認）:**
- 候選點 3km 內西醫一般診所實為約 11–12 家、醫美/美容約 59 家；舊版只抓到 16 家且全在 2.5–3km（最近僅 2.49km），漏掉 0.86km 樂誠、1.23km 樂安等。
- 原因一：`fetch_search_nearby(["doctor"])` 只取 Google type `doctor`，台灣診所多為 `medical_clinic`。
- 原因二：`searchNearby` 單次硬上限 20 筆、不分頁、按熱門度排序 → 回傳的是林口長庚旁大診所。

**Architecture:**
- `geo/grid.py`：`tile_centers(center, radius_km, step_km)` 純函式，產生覆蓋圓的子查詢中心，突破 20 筆上限。
- `analysis/competition.py`：`classify_place(name, types)` 純函式 → dental/tcm/aesthetic/western/other。
- `pipeline.collect_live`：對網格逐格 `fetch_search_nearby`（含 medical_clinic 等），依座標去重、分類，分別算 western 與 aesthetic 的距離加權有效家數，寫 `competition_*` 與 `competition_aesthetic_*`，geo 分 `clinics`(western) / `aesthetic`。
- `factors.py`：新增第 14 因子 `competition_aesthetic`（複用 `_competition_score`）。
- `config/specialties.yaml`：family/functional/weight/psych 用 `competition`（西醫池），`competition_aesthetic` 無；aesthetics 反之（competition 無、competition_aesthetic 最高）。
- `site/app.js` + `index.html` + `style.css`：what-if 權重滑桿（即時重算該科總分，純前端，用 breakdowns 既有 score）；header 資料新鮮度徽章（>40 天標紅）。
- `.github/workflows/refresh-and-deploy.yml`：移除 `schedule`（停用雲端月刷新，避免 degraded 覆蓋本機真值），保留 workflow_dispatch + push。
- `deploy/refresh.sh` + `com.clinicsiting.refresh.plist` + `install-schedule.sh`：本機 launchd 月度刷新→commit→push。

**Tech Stack:** Python 3.9/3.11、pytest、原生 JS、GitHub Actions/Pages、launchd。

---

## Task 1: geo/grid.py — 網格中心（純函式 + 測試）
- `tile_centers(center, radius_km, step_km)`：以 step_km 間距產生方格中心，保留落在 radius+step 內者；含中心點。
- 測試：3km/step1.2 → 含中心、所有點距中心 ≤ radius+step、數量 >1。

## Task 2: analysis/competition.py — 分類器（純函式 + 測試）
- 關鍵字集：DENTAL(牙醫/牙科)、TCM(中醫)、AESTHETIC_NAME(醫美/醫學美容/整形/微整/皮膚/美容/美學/做臉/美妍/紋繡/美睫/美甲/除毛)、AESTHETIC_TYPES(skin_care_clinic/beauty_salon/spa/massage_spa/nail_salon/hair_care/wellness_center/massage)。
- `classify_place(name, types)`：dental→tcm→aesthetic(name)→western(含「診所/專科」且非「醫院」)→aesthetic(type)→other。
- 測試：樂安診所→western；牙醫→dental；醫美/做臉→aesthetic；中醫→tcm；beauty_salon type 無診所字→aesthetic；長庚醫院→other（非 western）。

## Task 3: factors.py + config + cli — competition_aesthetic 第 14 因子
- ALL_FACTORS 插入 `competition_aesthetic`（competition 後）→ 14。
- build_factors 新增 competition_aesthetic（複用 `_competition_score`，real/missing）。
- factor_explanation 新增 competition_aesthetic 說明。
- config：factors 增列、negative_factors 增列；各科權重如上。
- cli SAMPLE_FACTORS 增 `competition_aesthetic`。
- 測試：test_factors ==13→==14、competition_aesthetic real/missing；test_pipeline ==13→==14。

## Task 4: pipeline.collect_live — 網格掃描競爭
- 以 `tile_centers` 逐格查 `fetch_search_nearby([broad types], …, sub_m)`，座標去重。
- `classify_place` 分 western / aesthetic；各算 `count_within` 與 `weighted_count_within`。
- 寫 raw：competition_count/weighted、competition_aesthetic_count/weighted；geo：clinics(western)、aesthetic。
- 失敗整段略過（交給 fill_degraded）。

## Task 5: #3 what-if 權重滑桿（前端）
- renderBreakdown：每列權重改 range(0–5) 滑桿；即時重算 Σ(score×w)/Σw 更新 tfoot「試算總分」；reset 還原原始權重。
- 純前端，無後端變更。

## Task 6: #5 資料新鮮度徽章（前端）
- header 加徽章，顯示最新快照日期（trend.dates 末筆）；距今 >40 天加 `.stale` 標紅。

## Task 7: #4 本機定期更新 + 停雲端排程
- workflow 移除 `schedule` 觸發。
- deploy/refresh.sh：cd repo→PYTHONPATH=src .venv/bin/python -m clinic_siting→git add site/data history.jsonl→commit [skip ci]→push；log 到 logs/refresh.log。
- com.clinicsiting.refresh.plist：StartCalendarInterval 每月 1 日 09:00。
- install-schedule.sh：複製到 ~/Library/LaunchAgents 並 load。

---

## 驗證
- `pytest` 全綠。
- 本機 live：`PYTHONPATH=src .venv/bin/python -m clinic_siting`，確認 western≈11–12、aesthetic≈59、含樂安/樂誠。
- commit/push → 等 Actions 部署 → curl 線上 geo.json 確認新 clinics/aesthetic。
