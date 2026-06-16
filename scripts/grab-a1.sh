#!/usr/bin/env bash
#
# grab-a1.sh — 掛機重試搶 Oracle A1.Flex（免費 4 OCPU/24GB，常 Out of host capacity）
#
# 用法：在「第二台 E2.1.Micro」上跑（24/7 掛機）。先裝好 OCI CLI 並 `oci setup config`，
#       填好下面「檔頭變數區」，然後：
#           chmod +x grab-a1.sh
#           nohup ./grab-a1.sh > grab-a1.log 2>&1 &
#           tail -f grab-a1.log
#
# 設定教學見 docs/guides/oci-grab-a1.md。
# ⚠️ 不含任何真實金鑰/OCID——所有 <...> 值由你自己填，別把填好的檔 commit 回 git。
#
set -u

# ───────────────────────── 檔頭變數區（自己填）─────────────────────────
# 從 Console 或 `oci ...` 查到的 OCID，貼進這裡（見 runbook 第 4 步）
COMPARTMENT_ID="<你的 compartment OCID>"
SUBNET_ID="<你的 subnet OCID>"
IMAGE_ID="<A1 Ubuntu image OCID>"
SSH_AUTHORIZED_KEYS_FILE="$HOME/.ssh/id_rsa.pub"   # A1 開機要塞的 public key

# 要搶的規格（免費上限 4 OCPU / 24GB；想保守可改 1 OCPU / 6GB 較易搶到）
OCPUS="4"
MEM_GB="24"
DISPLAY_NAME="albee-a1"

# 輪流嘗試的 availability domain（用 `oci iam availability-domain list` 的 name 填）
ADS=(
  "<AD-1 name，如 xxxx:AP-SINGAPORE-1-AD-1>"
  "<AD-2 name>"
  "<AD-3 name>"
)

RETRY_SECONDS=75   # 每輪間隔（保持 60–90s，別調太短以免被判濫用）
# ───────────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "開始搶 A1.Flex（${OCPUS} OCPU / ${MEM_GB}GB），輪 ${#ADS[@]} 個 AD，每輪間隔 ${RETRY_SECONDS}s"

round=0
while true; do
  round=$((round + 1))
  for AD in "${ADS[@]}"; do
    log "第 ${round} 輪 → 試 AD: ${AD}"

    # 嘗試開機。stderr/stdout 一起抓，方便判讀 capacity 訊息。
    OUTPUT=$(oci compute instance launch \
      --availability-domain "${AD}" \
      --compartment-id "${COMPARTMENT_ID}" \
      --shape "VM.Standard.A1.Flex" \
      --shape-config "{\"ocpus\": ${OCPUS}, \"memoryInGBs\": ${MEM_GB}}" \
      --image-id "${IMAGE_ID}" \
      --subnet-id "${SUBNET_ID}" \
      --display-name "${DISPLAY_NAME}" \
      --assign-public-ip true \
      --metadata "{\"ssh_authorized_keys\": \"$(cat "${SSH_AUTHORIZED_KEYS_FILE}")\"}" \
      --wait-for-state RUNNING \
      2>&1)
    STATUS=$?

    if [ ${STATUS} -eq 0 ]; then
      log "🎉 搶到了！A1 instance 已建立並 RUNNING。"
      echo "${OUTPUT}"
      log "下一步：Console 取 Public IP → 照 docs/guides/oci-grab-a1.md 第 6 步搬 bot。"
      exit 0
    fi

    # 沒搶到：印簡短原因（多半是 Out of host capacity）後換下一個 AD
    if echo "${OUTPUT}" | grep -qi "Out of host capacity"; then
      log "  ✗ ${AD}：Out of host capacity（容量滿，繼續等）"
    else
      # 其他錯誤（OCID 填錯、權限不足等）通常每輪都會重現——印全文方便排查
      log "  ✗ ${AD}：launch 失敗（非容量問題，請檢查變數）："
      echo "${OUTPUT}"
    fi
  done

  log "本輪所有 AD 都沒搶到，等 ${RETRY_SECONDS}s 再試…"
  sleep "${RETRY_SECONDS}"
done
