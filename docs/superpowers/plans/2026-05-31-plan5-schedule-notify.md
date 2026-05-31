# Plan 5 — 公開網站 + 月度自動更新 Implementation Plan

> **For agentic workers:** 用 TDD 逐步實作；編排層薄、純函式先測，部署與排程交給 GitHub Actions。

**Goal:** 把已完成的抓取→算分→快照→靜態站（Plan 1–4）串成單一刷新指令，公開託管於 GitHub Pages，並由 GitHub Actions 每月雲端自動刷新資料、重建並重新部署網站（不需本機開機）。對應設計規格 §4 資料流步驟 1、4，並以「隨時可看的公開網址」取代原 §4 步驟 5 的寄信通知。

**Architecture:**
- `runner.py` + `__main__.py`：`python -m clinic_siting` = `run_pipeline(live=True, site_dir=site)`，抓取算分寫快照重建站，印出本月排名。供本機手動執行與 CI 共用。
- `data_sources/env.py`：`get_key` 改為「環境變數優先、其次本地 .env」，讓 GitHub Actions secrets 與本機 .env 都能供金鑰。
- `.github/workflows/refresh-and-deploy.yml`：
  - `schedule` 每月 1 日 cron 觸發刷新（雲端）；`workflow_dispatch` 手動；`push`（site/ 變動）只重新部署。
  - 刷新後把 `site/data/*.json` 與 `history.jsonl` commit 回 repo（commit 訊息帶 `[skip ci]` 避免迴圈），再用官方 Pages actions 部署 `site/`。
  - 金鑰缺漏時 Google/TDX 因子由 `fill_degraded` 沿用上次快照的真值（首次種子由本機 live 跑產生並入版控）。
- `.gitignore`：`site/data/*.json` 改為入版控（Pages 要發佈的資料）；`logs/`、`.env` 忽略。

**Tech Stack:** Python 3.9（執行）／3.11（CI）、pytest、GitHub Actions、GitHub Pages。

> 設計演進：原規格 §4 步驟 5 的「n8n 寄信通知」經使用者確認改為**不寄信、改公開網站隨時看**；部署機制由「本機 launchd 常駐伺服器」進一步改為「GitHub Pages + Actions 雲端月度刷新」，使更新不依賴本機開機。

---

## Task 1: runner.py + __main__.py — 編排與進入點

**Files:**
- Create: `src/clinic_siting/runner.py`
- Create: `src/clinic_siting/__main__.py`
- Test: `tests/test_runner.py`

- `run_refresh(live=True, reference_dir, history_path, config_path, site_dir)`：`run_pipeline(live, site_dir)` 抓取算分寫快照重建站，回傳 snapshot。
- `main()`：`run_refresh()` 後印排名；`__main__.py` 呼叫 `main()`。
- 測試（離線決定性）：離線建站並回傳 5 科別 snapshot、落檔 history.json/geo.json；連跑兩次各追加一筆快照。

## Task 2: env.py — 環境變數優先

**Files:**
- Modify: `src/clinic_siting/data_sources/env.py`

- `get_key(name)`：`os.environ.get(name) or load_env().get(name)`，使 CI secrets 與本機 .env 皆可用，且本機行為不變。

## Task 3: GitHub Actions — 月度刷新 + Pages 部署

**Files:**
- Create: `.github/workflows/refresh-and-deploy.yml`
- Modify: `.gitignore`（`site/data/*.json` 入版控、忽略 `logs/`）

- 觸發：`schedule`（每月）、`workflow_dispatch`、`push`（site/ 變動只部署）。
- 權限：`contents: write`（commit 回刷新資料）、`pages: write`、`id-token: write`；`concurrency: pages`。
- 步驟：checkout → setup-python 3.11 → pip install → （非 push 才）`python -m clinic_siting` 刷新 → commit `site/data`+`history.jsonl`（`[skip ci]`）→ `configure-pages`/`upload-pages-artifact(path: site)`/`deploy-pages`。

---

## 部署與驗證

```bash
# 本機手動刷新（用 .env 的金鑰，產生高品質種子資料）
PYTHONPATH=src .venv/bin/python -m clinic_siting

# 建立公開 repo 並推送
gh repo create clinic-siting --public --source=. --remote=origin --push

# 啟用 Pages（來源＝GitHub Actions）
gh api -X POST repos/{owner}/clinic-siting/pages -f build_type=workflow

# 之後：每月 1 日 Actions 自動刷新並重新部署；亦可在 Actions 頁手動 Run。
```

## 可選強化
- 在 repo Settings → Secrets 加入 `GOOGLE_MAPS_API_KEY`、`TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`，讓雲端刷新也能抓即時競爭/交通資料（否則沿用本機種子的 degraded 值）。
