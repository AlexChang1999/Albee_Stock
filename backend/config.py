"""
設定管理
========
集中管理所有「設定值」與「環境變數」的地方。

為什麼要有這個檔案？
- 程式各處都需要 API 金鑰、資料庫位置等設定。
- 如果每個檔案都自己 os.getenv()，會很亂、容易出錯。
- 所以統一在這裡讀一次，其他檔案只要 from backend.config import settings 即可。
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- Windows 主控台編碼修正 ---
# Windows 預設主控台是 cp950，印中文/emoji 容易出現亂碼或崩潰。
# 這裡把輸出強制改成 UTF-8，避免新手踩到這個常見的坑。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 專案根目錄（這支檔案在 backend/ 裡，往上一層就是專案根目錄）
BASE_DIR = Path(__file__).parent.parent

# 載入 .env 檔案裡的環境變數
load_dotenv(BASE_DIR / ".env")


class Settings:
    """把所有設定集中成一個物件，方便取用。"""

    # --- Alpaca 設定 ---
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    # 是否為「模擬交易(Paper)」。只要網址裡有 "paper" 就視為模擬環境。
    # 這是一道安全保險：避免不小心用到真錢。
    IS_PAPER: bool = "paper" in os.getenv("ALPACA_BASE_URL", "paper").lower()

    # --- LINE 通知設定（之後再填，現在可留空） ---
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")

    # --- 資料庫設定 ---
    # 用 SQLite，資料庫檔案就放在專案根目錄，叫 albee_stock.db
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'albee_stock.db'}"

    def check(self) -> bool:
        """檢查必要設定有沒有填好，回傳 True/False。"""
        if not self.ALPACA_API_KEY or not self.ALPACA_SECRET_KEY:
            print("⚠️  尚未設定 Alpaca 金鑰，請檢查 .env 檔案。")
            return False
        return True


# 建立一個全域共用的設定實例
settings = Settings()
