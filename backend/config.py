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

    # --- 全系統唯一資料源（Phase 6 step-01）---
    # 抓 K 線的資料源，回測與實盤「共用同一個設定」，徹底消滅「回測用 A、實盤用 B」的分岔。
    # 可選 "alpaca"（預設）或 "yfinance"（免費）。想整套切資料源只改這一個環境變數，
    # 程式一行都不用動——這是「回測 = 實盤」鐵則的第一道（同源）。
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "alpaca")

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

    # --- AI 策略探勘 / 漏斗式篩選（改版 Phase 2）---
    # 盤前海選的候選股池（逗號分隔）。第一層用量價先粗篩，第二層才動用本機 Ollama，
    # 避免一次對幾百檔跑 LLM 把本機算力榨乾（漏斗式：先便宜後昂貴）。
    SCREENER_WATCHLIST: str = os.getenv(
        "SCREENER_WATCHLIST",
        "AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META,AMD,NFLX,INTC",
    )
    # 第一層量能門檻：最新一根的成交量 > 近 20 日均量 × 此倍數，才算「爆量」入選。
    SCREENER_VOLUME_RATIO: float = float(os.getenv("SCREENER_VOLUME_RATIO", "2.5"))
    # 第一層最多放幾檔進第二層（控制 LLM 呼叫次數，建議 5~10）。
    SCREENER_TOP_N: int = int(os.getenv("SCREENER_TOP_N", "8"))

    # --- 全自動護欄 / 模式 B 自動部署（改版 Phase 4）---
    # 「自動駕駛」：盤前排程跑 AI 海選，EV + 勝率同時超標就「無人工確認」自動建 Bot。
    # 風險最高，所以預設**關閉**，且與實盤雙閘獨立（開自動化 ≠ 開實盤，自動建的 Bot 仍預設 Paper）。
    AUTO_DEPLOY_ENABLED: bool = os.getenv("AUTO_DEPLOY_ENABLED", "false").lower() in ("1", "true", "yes")
    # 雙重門檻：兩個都要過才自動部署（EV 看絕對期望值、勝率看百分比）。
    AUTO_DEPLOY_EV_THRESHOLD: float = float(os.getenv("AUTO_DEPLOY_EV_THRESHOLD", "150"))
    AUTO_DEPLOY_WINRATE_THRESHOLD: float = float(os.getenv("AUTO_DEPLOY_WINRATE_THRESHOLD", "55"))
    # 最多同時自動建幾個 Bot（防一次梭哈）；每個 Bot 配多少資金。
    AUTO_DEPLOY_MAX_BOTS: int = int(os.getenv("AUTO_DEPLOY_MAX_BOTS", "5"))
    AUTO_DEPLOY_CASH_PER_BOT: float = float(os.getenv("AUTO_DEPLOY_CASH_PER_BOT", "1000"))
    # 盤前掃描的本機時刻（24 小時制的「時」）。美股盤前、開盤前跑一次。
    AUTO_DEPLOY_HOUR: int = int(os.getenv("AUTO_DEPLOY_HOUR", "8"))

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
