# ============================================
# Albee Stock 後端自動啟動器（給 Windows 工作排程器呼叫）
# --------------------------------------------
# 與 start_backend.bat 的差別：先檢查 8000 埠——後端已在跑就直接退出，
# 不會重複啟動（重複啟動會搶埠失敗、看門狗每 10 秒空轉重試）。
# 手動雙擊 start_backend.bat 的習慣不變，兩者可共存。
# ============================================

$root = Split-Path -Parent $PSScriptRoot  # scripts/ 的上一層 = 專案根

# 8000 埠已有人聽 = 後端活著 → 什麼都不做
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "後端已在執行（port 8000），跳過啟動。"
    exit 0
}

# 用最小化視窗啟動既有的一鍵 bat（保留看門狗 + 開機補跑行為）
Start-Process -FilePath "$root\start_backend.bat" -WorkingDirectory $root -WindowStyle Minimized
Write-Output "已啟動 Albee Stock 後端（看門狗模式，最小化視窗）。"
