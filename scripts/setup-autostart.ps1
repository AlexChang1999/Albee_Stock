# ============================================
# 註冊「每天開盤前自動啟動後端」的 Windows 排程工作（跑一次即可）
# --------------------------------------------
# 做三件事：
#   1. 每天 21:15（台北，美股夏令開盤 21:30 前 15 分）觸發 autostart_backend.ps1
#      —— 已在跑就跳過，不重複啟動。
#   2. 使用者登入時也觸發一次（白天重開機不用等到晚上）。
#   3. WakeToRun：電腦在「睡眠」會被喚醒來跑。⚠️ 完全關機叫不醒——
#      交易時段請讓電腦保持開機或睡眠。
#
# 用法（專案根目錄，一般權限即可）：
#   powershell -ExecutionPolicy Bypass -File scripts\setup-autostart.ps1        # 註冊 / 更新
#   powershell -ExecutionPolicy Bypass -File scripts\setup-autostart.ps1 -Remove # 移除
#
# 注意：美股冬令開盤是台北 22:30，21:15 啟動照樣涵蓋（後端休市時只是閒著，
# 不會亂下單——bot 掃描有開盤檢查）。
# ============================================

param([switch]$Remove)

$taskName = "AlbeeStock-Backend-AutoStart"
$root = Split-Path -Parent $PSScriptRoot
$launcher = "$root\scripts\autostart_backend.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "已移除排程工作：$taskName"
    exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$launcher`"" `
    -WorkingDirectory $root

$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At "21:15"),   # 開盤前（夏令 21:30 開盤）
    (New-ScheduledTaskTrigger -AtLogOn)              # 登入即啟動（白天重開機也接上）
)

# WakeToRun：睡眠中喚醒；AllowStartIfOnBatteries：筆電用電池也照跑
$settings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)  # 只管「啟動」，後端本身不受此限

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers `
        -Settings $settings -Description "Albee Stock：每天開盤前自動啟動交易後端（已在跑則跳過）" `
        -Force -ErrorAction Stop | Out-Null
} catch {
    Write-Output "❌ 註冊失敗：$($_.Exception.Message)"
    Write-Output "   多半是權限不足——請開「系統管理員 PowerShell」再跑一次本腳本。"
    exit 1
}

Write-Output "已註冊排程工作：$taskName"
Write-Output "  - 每天 21:15 自動啟動後端（含睡眠喚醒）"
Write-Output "  - 使用者登入時也會啟動一次"
Write-Output "  - 測試：Start-ScheduledTask -TaskName $taskName"
