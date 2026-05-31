#!/bin/bash
# 本機月度刷新：用 .env 的真實金鑰抓資料、算分、重建 site/，commit 並 push。
# push 會觸發 GitHub Actions 重新部署 Pages（不需本機開伺服器）。
# 由 launchd（com.clinicsiting.refresh.plist）每月呼叫；亦可手動執行。
set -euo pipefail

REPO="/Users/chenhungwen/Claude/店面選擇"
cd "$REPO"

mkdir -p logs
LOG="logs/refresh.log"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 開始刷新 =====" >>"$LOG"

# 先同步遠端，避免 push 被拒
git pull --rebase --autostash origin main >>"$LOG" 2>&1 || true

# 抓資料 + 算分 + 重建站
if PYTHONPATH=src "$REPO/.venv/bin/python" -m clinic_siting >>"$LOG" 2>&1; then
  echo "刷新成功" >>"$LOG"
else
  echo "!! 刷新失敗（見上方錯誤）；保留現有資料不 commit" >>"$LOG"
  exit 1
fi

# 只 commit 資料與歷史；無變動則略過
git add site/data history.jsonl
if git diff --cached --quiet; then
  echo "無資料變動，略過 commit" >>"$LOG"
else
  git commit -m "data: 本機月度刷新 $(date +%F) [skip ci]" >>"$LOG" 2>&1
  git push origin main >>"$LOG" 2>&1
  echo "已 push，GitHub Actions 將重新部署" >>"$LOG"
fi
echo "===== 完成 =====" >>"$LOG"
