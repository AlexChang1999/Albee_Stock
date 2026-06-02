"""
測試 Alpaca 連線
================
這支程式的目的：確認我們真的能連上 Alpaca 的 Paper Trading（模擬交易）帳戶。

它會做三件事：
1. 從 .env 讀取 API 金鑰
2. 查詢帳戶資訊（現金、購買力等）
3. 抓一檔股票（AAPL 蘋果）的最新報價

執行方式（在專案根目錄）：
    venv\\Scripts\\python.exe backend\\test_connection.py
"""

import os
import sys
from pathlib import Path

# Windows 主控台預設 cp950 印不出 emoji，這裡強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest


# ---------------------------------------------------------------
# 步驟 1：載入 .env 檔案裡的環境變數
# ---------------------------------------------------------------
# .env 在「專案根目錄」，而這支程式在 backend/ 資料夾裡，
# 所以要往上一層找。Path(__file__) 是這支檔案的路徑，
# .parent.parent 就是上一層（專案根目錄）。
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# 簡單檢查：金鑰有沒有讀到？沒讀到就直接提醒並結束。
if not API_KEY or not SECRET_KEY:
    print("❌ 找不到 API 金鑰！請確認 .env 檔案裡有填 ALPACA_API_KEY 和 ALPACA_SECRET_KEY")
    raise SystemExit(1)

print(f"✅ 已讀取金鑰，API_KEY 開頭為：{API_KEY[:4]}...（為安全只顯示前 4 碼）\n")


# ---------------------------------------------------------------
# 步驟 2：建立「交易用」客戶端，查詢帳戶資訊
# ---------------------------------------------------------------
# paper=True 代表連到「模擬交易」環境，不會用到真錢。
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

try:
    account = trading_client.get_account()
    print("===== 帳戶資訊 =====")
    print(f"帳戶狀態      : {account.status}")
    print(f"現金          : ${account.cash}")
    print(f"購買力        : ${account.buying_power}")
    print(f"投資組合總值  : ${account.portfolio_value}")
    print()
except Exception as e:
    print(f"❌ 連線帳戶失敗：{e}")
    print("→ 多半是 API 金鑰填錯，請回 Alpaca 網站重新確認 Paper Trading 的金鑰。")
    raise SystemExit(1)


# ---------------------------------------------------------------
# 步驟 3：建立「資料用」客戶端，抓 AAPL 最新報價
# ---------------------------------------------------------------
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

try:
    # 建立一個「要查哪幾檔股票最新報價」的請求
    request = StockLatestQuoteRequest(symbol_or_symbols="AAPL")
    latest_quote = data_client.get_stock_latest_quote(request)

    quote = latest_quote["AAPL"]
    print("===== AAPL 最新報價 =====")
    print(f"買價(bid): ${quote.bid_price}")
    print(f"賣價(ask): ${quote.ask_price}")
    print(f"報價時間 : {quote.timestamp}")
    print()
    print("🎉 連線測試全部成功！Alpaca 一切正常。")
except Exception as e:
    print(f"❌ 抓報價失敗：{e}")
    raise SystemExit(1)
