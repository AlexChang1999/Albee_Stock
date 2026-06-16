@echo off
chcp 65001 >nul
REM ============================================
REM Albee Stock 政治專討員一鍵啟動（Discord 鏡像頻道監聽）
REM 雙擊本檔即可啟動 political_watcher（會自動切到本檔所在資料夾）
REM
REM 鏈路：川普發文 → #一般(鏡像) → 本機 Ollama 判讀 → 偏空才推 #Albee-通知
REM 前提：1) Ollama 要先開（ollama serve）  2) .env 設好 POLITICAL_* 與 DISCORD_WEBHOOK_URL
REM ============================================
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [錯誤] 找不到 venv，請先執行 setup.bat 建立環境。
    pause
    exit /b 1
)

if not exist ".env" (
    echo [警告] 找不到 .env 檔，政治專討員無法連 Discord / 判讀。
    echo         請先複製 .env.example 為 .env 並填入 POLITICAL_* 設定。
    echo.
)

echo ============================================
echo  啟動 Albee Stock 政治專討員（看門狗模式）
echo  讀鏡像頻道貼文 -^> 本機 Ollama 判讀 -^> 偏空推 #Albee-通知
echo  程序若崩潰會自動在 10 秒後重啟
echo  按 Ctrl+C 再答 Y 可真正停止
echo ============================================
echo.

REM 看門狗迴圈：行程崩潰（斷網、Discord 重連失敗…）就等 10 秒自動重拉。
REM 與後端的 start_backend.bat 同款，人不在家時自己救自己。
:watchdog
venv\Scripts\python.exe -m backend.bots.political_watcher
echo.
echo [看門狗] 政治專討員結束（exit code %errorlevel%），10 秒後自動重啟... 按 Ctrl+C 放棄。
timeout /t 10 /nobreak >nul
goto watchdog
