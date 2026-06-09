@echo off
chcp 65001 >/dev/null
REM ============================================
REM Albee Stock 一鍵「背景」啟動：同時起後端 + 前端
REM 雙擊本檔：各開一個視窗在背景跑，console 不被佔住
REM ============================================
cd /d "%~dp0"

if not exist "venv\Scripts\uvicorn.exe" (
    echo [錯誤] 找不到 venv，請先執行 setup.bat 建立環境。
    pause
    exit /b 1
)

if not exist ".env" (
    echo [警告] 找不到 .env，後端可能無法連上 Alpaca。請先複製 .env.example 為 .env 並填金鑰。
    echo.
)

REM 確保資料庫 schema 最新（含本次新增的 automation_config 等表）
echo [1/3] 更新資料庫 schema（alembic upgrade head）...
venv\Scripts\alembic.exe upgrade head

REM 背景啟動後端（獨立視窗，標題 Albee-Backend）
echo [2/3] 背景啟動後端 API（http://127.0.0.1:8000/docs）...
start "Albee-Backend" venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000

REM 背景啟動前端（獨立視窗，標題 Albee-Frontend；首次會自動 npm install）
echo [3/3] 背景啟動前端（http://localhost:5173）...
start "Albee-Frontend" cmd /c "cd frontend && if not exist node_modules (npm install) && npm run dev"

echo.
echo ============================================
echo  已在背景啟動前後端（各自獨立視窗）：
echo    後端 http://127.0.0.1:8000/docs
echo    前端 http://localhost:5173
echo  關閉那兩個視窗即可停止。
echo ============================================
