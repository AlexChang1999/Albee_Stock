"""
設定管理
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

    # --- 實盤交易安全閥（第二道保險，預設關閉）---
    # 就算 ALPACA_BASE_URL 指到實盤(真錢)，沒有把這個明確設成 true，
    # 系統仍會「拒絕送出真錢單」。要動真錢必須同時：
    #   1) ALPACA_BASE_URL 用實盤網址（IS_PAPER 變 False）
    #   2) ALLOW_LIVE_TRADING=true
    # 兩道閘都開才會下真單，避免手滑或設定錯誤就燒到真錢。
    ALLOW_LIVE_TRADING: bool = os.getenv("ALLOW_LIVE_TRADING", "false").lower() in ("1", "true", "yes")

    # --- LINE 通知設定（之後再填，現在可留空） ---
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")

    # --- 資料庫設定 ---
    # 預設用 SQLite，資料庫檔案放在專案根目錄（albee_stock.db）。
    # 但允許用環境變數 DATABASE_URL 覆寫 → 未來要換 PostgreSQL，
    # 只要在 .env 設 DATABASE_URL=postgresql://... 即可，程式一行都不用改。
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'albee_stock.db'}",
    )

    # --- LLM 思考助手設定（Phase 5）---
    # 用「OpenAI 相容介面」串接，所以同一套程式可接很多家：
    #   - 本機 Ollama（預設，完全免費）：base_url=http://localhost:11434/v1
    #   - Google Gemini 免費層 / Groq 免費層 / 甚至 OpenAI、Anthropic 也都有相容端點。
    # 想換供應商只要改這三個環境變數，程式一行都不用動。
    # 預設指向本機 Ollama，金鑰隨便填（Ollama 不檢查）。沒裝/沒開 Ollama 時，
    # /chat 會回 400 並提示怎麼啟動，不會讓系統崩潰。
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.1")

    # --- 即時報價推送（Phase 6）---
    # 後端每隔幾秒向 Alpaca 拉一次最新成交價，再透過 WebSocket 推給前端。
    # 數字越小越即時、但越耗 Alpaca 的 REST 額度；5 秒對學習/觀察很夠用。
    QUOTE_POLL_INTERVAL_SEC: float = float(os.getenv("QUOTE_POLL_INTERVAL_SEC", "5"))
    # --- LLM 外送閘（隱私安全閥，預設關）---
    # 助手會把「策略方案 + 回測歷史 + 探討筆記」注入 prompt 當記憶。
    # 若 LLM_BASE_URL 指向**外部雲端**服務，這些資料就會離開本機、送到第三方。
    # 仿照實盤雙閘的精神：預設只允許本機（localhost/127.0.0.1）。
    # 要用雲端供應商，必須明確把這個設成 true，等於「我知道資料會外送」。
    LLM_ALLOW_CLOUD: bool = os.getenv("LLM_ALLOW_CLOUD", "false").lower() in ("1", "true", "yes")

    # --- 全自動護欄／模式 B（自動駕駛）設定（Phase 4）---
    # 「模式 B」＝後端週期性自動海選，當策略 EV 與勝率同時達標就「無需人工確認」
    # 自動建立 Bot 並掛上排程。這是整套系統風險最高的功能，因此：
    #   1) 預設整個關閉（AUTO_PILOT_ENABLED=false），要明確開才會啟動。
    #   2) 自動 Bot 有「數量上限」（AUTO_PILOT_MAX_BOTS），防失控暴增。
    #   3) 真正下單仍走 alpaca_client 的「實盤雙閘安全閥」——模式 B 不繞過它，
    #      所以就算開了自動駕駛，沒開實盤雙閘也只會在 Paper（模擬）下單，不燒真錢。
    AUTO_PILOT_ENABLED: bool = os.getenv("AUTO_PILOT_ENABLED", "false").lower() in ("1", "true", "yes")
    # EV（期望值）門檻：海選結果的最佳策略 EV ≥ 此值才考慮自動部署。藍圖建議 150。
    AUTO_PILOT_MIN_EV: float = float(os.getenv("AUTO_PILOT_MIN_EV", "150"))
    # 勝率門檻（百分比）：win_rate_pct ≥ 此值才考慮自動部署。藍圖建議 55。
    AUTO_PILOT_MIN_WIN_RATE: float = float(os.getenv("AUTO_PILOT_MIN_WIN_RATE", "55"))
    # 自動海選頻率（秒）：預設 3600（每小時掃一次），避免太頻繁吃算力。
    AUTO_PILOT_INTERVAL_SEC: int = int(os.getenv("AUTO_PILOT_INTERVAL_SEC", "3600"))
    # 自動建立的 Bot 數量上限（達上限後不再自動部署，防失控）。預設 5。
    AUTO_PILOT_MAX_BOTS: int = int(os.getenv("AUTO_PILOT_MAX_BOTS", "5"))
    # 每個自動 Bot 的單筆下單金額（美元）。預設 1000。
    AUTO_PILOT_TRADE_AMOUNT: float = float(os.getenv("AUTO_PILOT_TRADE_AMOUNT", "1000"))

    # --- 探討（檢討）檔案記憶（Phase 5）---
    # 思考助手把每次事後檢討寫成 markdown 檔放這個資料夾，並用 INDEX.md 當「路標」，
    # 之後寫新檢討前會先讀路標、挑相關舊探討來參考（越來越聰明）。
    # 預設放專案根目錄的 explorations/（會進 git）。可用環境變數覆寫位置。
    EXPLORATIONS_DIR: str = os.getenv(
        "EXPLORATIONS_DIR", str(BASE_DIR / "explorations")
    )

    def check(self) -> bool:
        """檢查必要設定有沒有填好，回傳 True/False。"""
        if not self.ALPACA_API_KEY or not self.ALPACA_SECRET_KEY:
            print("⚠️  尚未設定 Alpaca 金鑰，請檢查 .env 檔案。")
            return False
        return True


# 建立一個全域共用的設定實例
settings = Settings()
