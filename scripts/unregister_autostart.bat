@echo off
chcp 65001 >nul
REM ============================================================
REM Albee Stock 取消開機常駐化（Phase 10 step-07）
REM ------------------------------------------------------------
REM 移除 register_autostart.bat 建立的「登入時自動啟動後端」工作。
REM 移除後，開機就不再自動拉起後端（要手動雙擊 start_backend.bat）。
REM 用法：對著本檔按右鍵「以系統管理員身分執行」。
REM ============================================================

set "TASK_NAME=AlbeeStockBackend"

echo 移除開機常駐工作：%TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% neq 0 (
    echo.
    echo [提醒] 移除失敗：可能本來就沒註冊，或權限不足（試試以系統管理員身分執行）。
    pause
    exit /b 1
)

echo.
echo [完成] 已移除。開機不再自動啟動後端。
pause
