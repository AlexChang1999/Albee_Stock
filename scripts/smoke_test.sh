#!/usr/bin/env bash
# ============================================================
# 線上煙霧測試（驗「已經跑起來的服務」）
# ============================================================
# 比 deploy.sh 原本只 `curl GET /`（看服務活著）更進一步：實打幾個功能性端點，
# 確認 DB 查得到、各 router 沒掛、回的是預期內容。任一端點失敗 → exit 1（給 deploy 觸發回滾）。
#
# 用法（repo 根目錄）：
#   bash scripts/smoke_test.sh                       # 預設打本機 http://127.0.0.1:8000
#   bash scripts/smoke_test.sh http://127.0.0.1:8000 # 雲端 VM 上指定 BASE_URL
set -uo pipefail   # 不用 -e：要讓每個 check 都跑完再彙總，而非第一個失敗就中斷

BASE="${1:-http://127.0.0.1:8000}"
fail=0

# check <path> <期望出現在回應中的關鍵字>
check() {
  local path="$1" want="$2" body
  body="$(curl -fsS "${BASE}${path}" 2>/dev/null)" || { echo "❌ ${path} 連不上"; fail=1; return; }
  if [[ "$body" == *"$want"* ]]; then
    echo "✅ ${path}"
  else
    echo "❌ ${path} 回應異常: ${body:0:120}"
    fail=1
  fi
}

echo "▶ 線上 smoke @ ${BASE}"
check "/"           "paper_trading"   # 健康端點（同 deploy 健檢）
check "/status"     "is_paper"        # 交易環境旗標
check "/bots"       "["               # 應回 JSON 陣列（純讀 DB）
check "/strategies" "value"           # 策略清單 [{value,label}]
check "/positions"  "["               # 無金鑰也應優雅回 []
check "/reminders"  "["               # 前端提醒橫幅資料

if [[ $fail -eq 0 ]]; then
  echo "🎉 線上 smoke 全過"
else
  echo "🔥 有端點失敗"
  exit 1
fi
