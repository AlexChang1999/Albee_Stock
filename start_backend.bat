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
echo  啟動 Albee Stock 後端 API（看門狗模式）
echo  文件位置: http://127.0.0.1:8000/docs
echo  後端若崩潰會自動在 10 秒後重啟（重啟時會觸發開機補跑）
echo  按 Ctrl+C 再答 Y 可真正停止
echo ============================================
echo.

REM 看門狗迴圈：行程崩潰（斷網炸掉、未捕捉例外…）就等 10 秒自動重拉，
REM 配合後端的「開機補跑」，重啟後當天漏掉的每日 job 會自動補上。
REM 人睡覺 / 不在家時系統自己救自己；Ctrl+C 中斷會問是否終止批次，答 Y 即可離開。
:watchdog
venv\Scripts\uvicorn.exe backend.main:app --reload
echo.
echo [看門狗] 後端結束（exit code %errorlevel%），10 秒後自動重啟... 按 Ctrl+C 放棄。
timeout /t 10 /nobreak >nul
goto watchdog
