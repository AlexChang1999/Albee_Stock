@echo off
chcp 65001 >nul
REM ============================================
REM Albee Stock 前端一鍵啟動
REM 雙擊本檔即可啟動 React (Vite) 前端
REM ============================================
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo [提示] 尚未安裝前端套件，先執行 npm install...
    call npm install
)

echo ============================================
echo  啟動 Albee Stock 前端
echo  畫面位置: http://localhost:5173
echo  按 Ctrl+C 可停止
echo ============================================
echo.

call npm run dev

pause
