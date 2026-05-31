#!/bin/bash
# 安裝/重新載入本機月度刷新 launchd 排程。可重複執行（會先卸載舊的）。
set -euo pipefail

REPO="/Users/chenhungwen/Claude/店面選擇"
LABEL="com.clinicsiting.refresh"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"

mkdir -p "$AGENTS"
cp "$REPO/deploy/$LABEL.plist" "$PLIST"
chmod +x "$REPO/deploy/refresh.sh"

# 先卸載（忽略不存在的錯誤）再載入
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "已安裝排程：$LABEL（每月 1 日 09:00）"
echo "檢查：launchctl list | grep clinicsiting"
echo "立即測試一次：launchctl start $LABEL，再看 $REPO/logs/refresh.log"
