@echo off
chcp 65001 >nul
REM ============================================
REM Albee Stock 後端一鍵啟動
REM 雙擊本檔即可啟動 FastAPI 後端（會自動切到本檔所在資料夾）
REM ============================================
cd /d "%~dp0"

if not exist "venv\Scripts\uvicorn.exe" (
    echo [錯誤] 找不到 venv，請先執行 setup.bat 建立環境。
    pause
    exit /b 1
)

if not exist ".env" (
    echo [警告] 找不到 .env 檔，後端可能無法連上 Alpaca。
    echo         請先複製 .env.example 為 .env 並填入金鑰。
    echo.
)

echo ============================================
echo  啟動 Albee Stock 後端 API
echo  文件位置: http://127.0.0.1:8000/docs
echo  按 Ctrl+C 可停止伺服器
echo ============================================
echo.

venv\Scripts\uvicorn.exe backend.main:app --reload

pause
