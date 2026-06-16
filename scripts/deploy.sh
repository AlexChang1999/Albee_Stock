#!/usr/bin/env bash
# ============================================================
# VM 部署腳本（在 Oracle VM 上執行；由 GitHub Actions deploy job 透過 SSH 呼叫）
# ============================================================
# 流程：記住目前版本 → 拉新碼 → 裝依賴 → 套 DB 遷移 → 重啟服務 → 健康檢查
#       → 健檢失敗就回滾到上一版（含重套遷移、重啟），確保 VM 永遠停在「能跑」的版本。
#
# 用法（在 repo 根目錄）：bash scripts/deploy.sh [branch]
#   branch 預設 main。
#
# 前置（VM 一次性設定）：
#   - venv 在 ~/Albee_Stock/venv（見 docs/guides/free-vm-deployment.md）
#   - 給 deploy 帳號「免密碼 sudo 重啟該服務」權限，否則 ssh 非互動會卡：
#       echo "$USER ALL=(root) NOPASSWD: /bin/systemctl restart albee-backend" \
#         | sudo tee /etc/sudoers.d/albee-deploy
set -euo pipefail

BRANCH="${1:-main}"
SERVICE="albee-backend"
HEALTH_URL="http://127.0.0.1:8000/"

# 切到 repo 根目錄（腳本在 scripts/ 底下）
cd "$(dirname "$0")/.."

PREV="$(git rev-parse HEAD)" # 記住目前版本，供回滾
echo "▶ 目前版本 ${PREV:0:8}，準備部署 origin/${BRANCH}"

# --- 拉新碼 ---
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"
NEW="$(git rev-parse HEAD)"
echo "▶ 已更新到 ${NEW:0:8}"

deploy_current() {
  venv/bin/pip install -q -r requirements.txt
  venv/bin/alembic upgrade head # DB 遷移到頂（含唯一鍵等）
  sudo systemctl restart "$SERVICE"
  sleep 5
}

deploy_current

# --- 健康檢查：失敗就回滾 ---
if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "✅ 部署成功，健康檢查通過 @ ${NEW:0:8}"
else
  echo "❌ 健康檢查失敗 → 回滾到 ${PREV:0:8}"
  git reset --hard "$PREV"
  deploy_current
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "↩️  已回滾到上一版且健康檢查通過 @ ${PREV:0:8}（本次部署失敗）"
  else
    echo "🔥 回滾後仍不健康，請人工介入：journalctl -u $SERVICE -n 50"
  fi
  exit 1
fi
