# Plan 5 — 月度排程 + 常駐網站 Implementation Plan

> **For agentic workers:** 用 TDD 逐步實作；編排層薄、純函式先測，外部 IO（launchd）以腳本隔離。

**Goal:** 把已完成的抓取→算分→快照→靜態站（Plan 1–4）串成單一可排程的刷新指令，並用常駐本機伺服器把網站固定在一個可隨時點進去看的網址（http://localhost:8080），對應設計規格 §4 資料流步驟 1、4。

**Architecture:**
- `runner.py`：`run_refresh()` 編排——呼叫 `run_pipeline(live=True, site_dir=site)` 抓取算分寫快照並重建站台；`main()` 印出本月排名。
- `__main__.py`：`python -m clinic_siting` 進入點。
- `deploy/`：兩個 LaunchAgent ＋ 一支安裝腳本
  - `com.chenhungwen.clinic-siting.plist`：每月 1 號 03:00 觸發刷新。
  - `com.chenhungwen.clinic-siting.serve.plist`：常駐 `python -m http.server 8080 --directory site`，開機即起、掛掉自動重啟。
  - `install-schedule.sh {install|uninstall|run|status}`：一次安裝/卸載兩個服務。

**Tech Stack:** Python 3.9（`from __future__ import annotations`）、pytest、Python stdlib `http.server`、macOS launchd。

> 設計演進：原規格 §4 步驟 5 的「n8n 寄信通知」經使用者確認改為**不寄信**，改以常駐網站隨時查看取代，故移除 notify 模組。

---

## Task 1: runner.py + __main__.py — 編排與進入點

**Files:**
- Create: `src/clinic_siting/runner.py`
- Create: `src/clinic_siting/__main__.py`
- Test: `tests/test_runner.py`

- `run_refresh(live=True, reference_dir, history_path, config_path, site_dir)`：`run_pipeline(live, site_dir)` 抓取算分寫快照重建站，回傳 snapshot。
- `main()`：`run_refresh()` 後印排名；`__main__.py` 呼叫 `main()`。
- 測試（離線決定性）：離線建站並回傳 5 科別 snapshot、落檔 history.json/geo.json；連跑兩次各追加一筆快照。

## Task 2: deploy/ — launchd 月度排程 + 常駐網站

**Files:**
- Create: `deploy/com.chenhungwen.clinic-siting.plist`（refresh）
- Create: `deploy/com.chenhungwen.clinic-siting.serve.plist`（serve）
- Create: `deploy/install-schedule.sh`

- refresh plist：`StartCalendarInterval` Day=1 Hour=3 Minute=0；`WorkingDirectory` 與 `PYTHONPATH=…/src`；`ProgramArguments` 為 `.venv/bin/python -m clinic_siting`；stdout/stderr 導向 `logs/`。
- serve plist：`ProgramArguments` 為 `.venv/bin/python -m http.server 8080 --directory …/site`；`RunAtLoad`＋`KeepAlive` 為 true；log 導向 `logs/`。
- `install-schedule.sh`：複製兩個 plist 至 `~/Library/LaunchAgents` 並 `launchctl load`／`unload`／`start`／`list`。

---

## 安裝與驗證

```bash
# 手動跑一次（live 抓取 + 重建站）
PYTHONPATH=src .venv/bin/python -m clinic_siting

# 安裝（每月排程 + 常駐網站）
./deploy/install-schedule.sh install
# 開瀏覽器看網站
open http://localhost:8080
# 立即手動刷新驗證（輸出見 logs/refresh.out.log）
./deploy/install-schedule.sh run
# 查看載入狀態 / 卸載
./deploy/install-schedule.sh status
./deploy/install-schedule.sh uninstall
```
