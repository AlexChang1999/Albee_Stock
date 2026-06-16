#!/usr/bin/env bash
# ============================================================
# VM 部署腳本（在 Oracle VM 上執行；由 GitHub Actions deploy job 透過 SSH 呼叫）
# ============================================================
# 流程：記住目前版本(含 DB revision) → 拉新碼 → 裝依賴 → 套 DB 遷移 → 重啟服務
#       → 健康檢查(重試最多 ~60s) → 健檢失敗就回滾到上一版
#       （先用「新碼」把 DB downgrade 回部署前 revision，再 reset 舊碼、重啟），
#       確保 VM 永遠停在「能跑」且 code/schema 一致的版本。
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

PREV="$(git rev-parse HEAD)" # 記住目前版本（git），供回滾
# 記住部署前的 DB revision（供回滾時 downgrade 回這個點）。
# 用 `|| true` 避免 alembic / grep 無輸出時在 set -e 下中斷整個腳本。
PREV_REV="$(venv/bin/alembic current 2>/dev/null | grep -oE '[0-9a-f]{12}' | head -1 || true)"
echo "▶ 目前版本 ${PREV:0:8}（DB revision: ${PREV_REV:-無}），準備部署 origin/${BRANCH}"

# --- 拉新碼 ---
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"
NEW="$(git rev-parse HEAD)"
echo "▶ 已更新到 ${NEW:0:8}"

# 裝依賴 + DB 遷移到頂 + 重啟服務
deploy_current() {
  venv/bin/pip install -q -r requirements.txt
  venv/bin/alembic upgrade head # DB 遷移到頂（含唯一鍵等）
  sudo systemctl restart "$SERVICE"
}

# 健康檢查：重試最多 ~60s（新後端開機要時間連 DB / import，單發 curl 會誤判失敗）
health_check() {
  local tries="${1:-20}" i
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

deploy_current

# --- 健康檢查 + 線上煙霧測試：失敗就回滾 ---
# health_check 只確認服務活著（curl /）；smoke_test 再多驗幾個功能端點真的回得了資料
# （DB 查得到、router 沒掛）。兩者皆過才算部署成功，任一失敗都走下面的回滾。
if health_check && bash scripts/smoke_test.sh "$HEALTH_URL"; then
  echo "✅ 部署成功，健康檢查 + 煙霧測試通過 @ ${NEW:0:8}"
else
  echo "❌ 健康檢查失敗 → 回滾到 ${PREV:0:8}"
  # 先用「新碼」把 DB downgrade 回部署前 revision——只有新碼帶得齊所有 migration 檔，
  # 才下得了行；reset 成舊碼後就少了新增的 revision 檔、downgrade 會找不到。
  if [ -n "$PREV_REV" ]; then
    echo "↩️  DB 回滾：alembic downgrade ${PREV_REV}"
    venv/bin/alembic downgrade "$PREV_REV" || echo "⚠️ DB downgrade 失敗，請人工檢查 schema"
  else
    echo "⚠️ 無法判定部署前 DB revision，跳過 DB 回滾（請人工檢查 schema）"
  fi
  # 再把程式碼 reset 回舊版並重啟。此時 DB 已回到 PREV_REV，與舊碼 head 一致，
  # 不需（也不可）再 alembic upgrade head——舊碼缺新 revision 檔會直接報錯。
  git reset --hard "$PREV"
  venv/bin/pip install -q -r requirements.txt
  sudo systemctl restart "$SERVICE"
  if health_check; then
    echo "↩️  已回滾到上一版且健康檢查通過 @ ${PREV:0:8}（本次部署失敗）"
  else
    echo "🔥 回滾後仍不健康，請人工介入：journalctl -u $SERVICE -n 50"
  fi
  exit 1
fi
