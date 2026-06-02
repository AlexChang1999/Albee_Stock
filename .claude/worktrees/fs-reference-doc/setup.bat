@echo off
chcp 65001 >nul
REM ============================================
REM Albee Stock 環境一鍵設置
REM 換新電腦 git clone 後，雙擊本檔即可建好整個開發環境
REM （建立 venv、安裝後端套件、安裝前端套件、產生 .env）
REM ============================================
cd /d "%~dp0"

echo ============================================
echo  Albee Stock 環境設置開始
echo ============================================
echo.

REM --- 檢查 Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 python，請先安裝 Python 3.13：https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- 1) 建立虛擬環境 ---
if exist "venv\Scripts\python.exe" (
    echo [1/5] venv 已存在，略過建立。
) else (
    echo [1/5] 建立虛擬環境 venv...
    python -m venv venv
)

REM --- 2) 安裝後端套件 ---
echo [2/5] 安裝後端套件 ^(requirements.txt^)...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

REM --- 3) 產生 .env ---
if exist ".env" (
    echo [3/5] .env 已存在，略過。^(請自行確認金鑰已填妥^)
) else (
    echo [3/5] 從 .env.example 複製產生 .env...
    copy ".env.example" ".env" >nul
    echo        請用編輯器打開 .env 並填入 Alpaca 金鑰！
)

REM --- 4) 建立/升級資料庫 schema（用 Alembic 遷移） ---
echo [4/5] 建立/升級資料庫 schema ^(alembic upgrade head^)...
venv\Scripts\alembic.exe upgrade head

REM --- 5) 安裝前端套件 ---
echo [5/5] 安裝前端套件 ^(npm install^)...
cd frontend
call npm install
cd ..

echo.
echo ============================================
echo  設置完成！
echo  - 啟動後端：雙擊 start_backend.bat
echo  - 啟動前端：雙擊 start_frontend.bat
echo  - 測試連線：venv\Scripts\python.exe backend\test_connection.py
echo ============================================
pause
