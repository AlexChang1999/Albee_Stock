"""
API 端點測試
============
用 FastAPI 的 TestClient 直接在程式內呼叫 API，驗證後端能正常運作。
（不需要另外啟動伺服器）

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_api.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from backend.main import app


def run_tests():
    # with 區塊會觸發 app 的 lifespan（初始化資料庫）
    with TestClient(app) as client:
        # 1) 健康檢查
        r = client.get("/")
        assert r.status_code == 200, r.text
        print("✅ GET / ：", r.json())

        # 2) 查帳戶（會實際連 Alpaca）
        r = client.get("/account")
        assert r.status_code == 200, f"查帳戶失敗：{r.text}"
        print("✅ GET /account ：現金 =", r.json()["cash"])

        # 3) 建立一個 Bot
        new_bot = {
            "name": "測試-AAPL均線交叉",
            "strategy": "ma_crossover",
            "symbol": "AAPL",
            "params": {"short_window": 5, "long_window": 20},
            "trade_amount": 1000,
        }
        r = client.post("/bots", json=new_bot)
        assert r.status_code == 200, r.text
        bot_id = r.json()["id"]
        print(f"✅ POST /bots ：建立成功，id={bot_id}")

        # 4) 列出 Bot
        r = client.get("/bots")
        assert r.status_code == 200, r.text
        bots = r.json()
        assert any(b["id"] == bot_id for b in bots), "列表裡找不到剛建的 Bot"
        print(f"✅ GET /bots ：目前共有 {len(bots)} 個 Bot")

    print("\n🎉 API 測試全部通過！")


if __name__ == "__main__":
    run_tests()
