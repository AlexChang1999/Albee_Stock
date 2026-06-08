@echo off
chcp 65001 >nul
REM ============================================================
REM Albee Stock 開機常駐化（Phase 10 step-07）
REM ------------------------------------------------------------
REM 在 Windows「工作排程器」註冊一個「登入時自動啟動後端」的工作。
REM 登入後 → 自動跑根目錄的 start_backend.bat → 後端起來 → APScheduler
REM 接回啟用中的 Bot + 盤前自動部署 + 常駐機會掃描（lifespan 已處理）。
REM
REM 純 ops：不碰任何交易邏輯。常駐跑的仍是 Paper，真錢仍受實盤雙閘 + 董事會核准把關。
REM
REM 用法：對著本檔按右鍵「以系統管理員身分執行」（建立排程工作需要權限）。
REM 移除：執行同資料夾的 unregister_autostart.bat。
REM ============================================================

REM 工作名稱（移除時要用同一個名字）
set "TASK_NAME=AlbeeStockBackend"

REM 專案根目錄 = 本檔（在 scripts\）的上一層
set "ROOT=%~dp0.."
REM 正規化成絕對路徑
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "TARGET=%ROOT%\start_backend.bat"

if not exist "%TARGET%" (
    echo [錯誤] 找不到 %TARGET%
    echo         請確認本檔放在專案的 scripts\ 資料夾下。
    pause
    exit /b 1
)

echo ============================================================
echo  註冊開機常駐工作
echo  工作名稱：%TASK_NAME%
echo  登入時執行：%TARGET%
echo ============================================================

REM /SC ONLOGON：目前使用者登入時觸發
REM /RL LIMITED：以一般權限執行（不需要最高權限跑後端）
REM /F：若同名工作已存在則覆寫
schtasks /Create /TN "%TASK_NAME%" /SC ONLOGON /TR "\"%TARGET%\"" /RL LIMITED /F

if %errorlevel% neq 0 (
    echo.
    echo [失敗] 註冊工作失敗（多半是權限不足）。
    echo         請改用「以系統管理員身分執行」本檔。
    pause
    exit /b 1
)

echo.
echo [完成] 已註冊。下次登入 Windows 會自動啟動後端。
echo        想立刻測試可執行：schtasks /Run /TN "%TASK_NAME%"
echo        詳細說明見 docs\phase-10-ai-company\ops-autostart.md
pause
