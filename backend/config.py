"""
設定管理
集中管理所有「設定值」與「環境變數」的地方。

為什麼要有這個檔案？
- 程式各處都需要 API 金鑰、資料庫位置等設定。
- 如果每個檔案都自己 os.getenv()，會很亂、容易出錯。
- 所以統一在這裡讀一次，其他檔案只要 from backend.config import settings 即可。

設定分區（Phase 6 step-10 整理）：依領域分段、加區段註解，方便快速定位：
  Alpaca / 資料源 / 資料庫 / LLM / Screener / Automation /
  回測成本(P6) / 樣本外 OOS(P6) / 情緒閘(P6) / 組合風控(P6) / 即時報價 / Explorations
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
    """把所有設定集中成一個物件，方便取用（依領域分區，見檔頭說明）。"""

    # ========================================================
    # Alpaca 交易 / 資料 API
    # ========================================================
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

    # --- Alpaca 資料 API 限流（免費版約 200 req/min）---
    # 批次化抓取後請求數大降，這是「保險絲」不是常態路徑：額度內直接放行，
    # 超量才 sleep 等補充，避免標的一多就被 429 打爆。0 = 不限流（測試 / 付費方案用）。
    ALPACA_RATE_LIMIT_PER_MIN: int = int(os.getenv("ALPACA_RATE_LIMIT_PER_MIN", "200"))

    # ========================================================
    # 全系統唯一資料源（Phase 6 step-01）
    # ========================================================
    # 抓 K 線的資料源，回測與實盤「共用同一個設定」，徹底消滅「回測用 A、實盤用 B」的分岔。
    # 可選 "alpaca"（預設）或 "yfinance"（免費）。想整套切資料源只改這一個環境變數，
    # 程式一行都不用動——這是「回測 = 實盤」鐵則的第一道（同源）。
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "alpaca")

    # 並行抓取的執行緒數：給「只能逐筆打」的 I/O 用（FRED 多序列、RSS 多 feed）。
    # 批次 API（一次請求抓多檔 K 線 / 報價）不需要這個。I/O-bound 用 threads 即夠。
    FETCH_MAX_WORKERS: int = int(os.getenv("FETCH_MAX_WORKERS", "4"))

    # ========================================================
    # 多年 OHLCV 本機快取（Phase 11 step-02）
    # ========================================================
    # 「整個歷史」回測（如 days=3650）不該每次都向 Alpaca / yfinance 重抓：缺的區間才補抓、
    # 抓回來寫進本機 parquet 快取，已有的命中快取不重打（services/bar_cache.py 包在 get_bars 外層）。
    # 快取檔放這個資料夾（按 {source}/{symbol} 分開存，不混存），預設 data/cache/bars/（gitignore，不進版控）。
    BAR_CACHE_DIR: str = os.getenv("BAR_CACHE_DIR", str(BASE_DIR / "data" / "cache" / "bars"))

    # ========================================================
    # 總經 / 環境資料（Phase 11 step-01）— FRED 聯準會經濟數據
    # ========================================================
    # 讓回測吃得到「環境因子」（非農就業、失業率、聯邦基金利率、CPI、公債殖利率、VIX）。
    # 資料源是 FRED（聖路易聯準會，免費，需自行申請免費 API key）。沿用「本機優先 / 免費」與
    # LLM 一樣的「優雅降級」：沒填 key → 整個總經功能靜默跳過，不另設開關、也不影響其他功能。
    #   - FRED_API_KEY：到 https://fred.stlouisfed.org/docs/api/api_key.html 免費申請。留空＝關閉。
    #   - MACRO_SERIES：要追蹤的 FRED 序列代號（逗號分隔）。
    #   - MACRO_DEFAULT_LAG_DAYS：未知序列的「發布落差」天數預設（point-in-time 防偷看未來；
    #     各序列的精確落差在 services/macro_data.py 的對照表，這裡只當 fallback）。
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    MACRO_SERIES: str = os.getenv(
        "MACRO_SERIES", "PAYEMS,UNRATE,FEDFUNDS,CPIAUCSL,DGS10,DGS2,VIXCLS"
    )
    MACRO_DEFAULT_LAG_DAYS: int = int(os.getenv("MACRO_DEFAULT_LAG_DAYS", "35"))

    # ========================================================
    # 資料庫
    # ========================================================
    # 預設用 SQLite，資料庫檔案放在專案根目錄（albee_stock.db）。
    # 但允許用環境變數 DATABASE_URL 覆寫 → 未來要換 PostgreSQL，
    # 只要在 .env 設 DATABASE_URL=postgresql://... 即可，程式一行都不用改。
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'albee_stock.db'}",
    )

    # ========================================================
    # LLM 思考助手（Phase 5）
    # ========================================================
    # 用「OpenAI 相容介面」串接，所以同一套程式可接很多家：
    #   - 本機 Ollama（預設，完全免費）：base_url=http://localhost:11434/v1
    #   - Google Gemini 免費層 / Groq 免費層 / 甚至 OpenAI、Anthropic 也都有相容端點。
    # 想換供應商只要改這三個環境變數，程式一行都不用動。
    # 預設指向本機 Ollama，金鑰隨便填（Ollama 不檢查）。沒裝/沒開 Ollama 時，
    # /chat 會回 400 並提示怎麼啟動，不會讓系統崩潰。
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.1")

    # --- LLM 外送閘（隱私安全閥，預設關）---
    # 助手會把「策略方案 + 回測歷史 + 探討筆記」注入 prompt 當記憶。
    # 若 LLM_BASE_URL 指向**外部雲端**服務，這些資料就會離開本機、送到第三方。
    # 仿照實盤雙閘的精神：預設只允許本機（localhost/127.0.0.1）。
    # 要用雲端供應商，必須明確把這個設成 true，等於「我知道資料會外送」。
    LLM_ALLOW_CLOUD: bool = os.getenv("LLM_ALLOW_CLOUD", "false").lower() in ("1", "true", "yes")

    # ========================================================
    # AI 策略探勘 / 漏斗式篩選（改版 Phase 2）
    # ========================================================
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

    # 因子數值表（Phase 10 step-03）保留天數：常駐掃描每輪順手把 watchlist 各檔因子落表，
    # 超過此天數的舊快照會被修剪，避免 DB 無上限膨脹。0 = 不修剪（保留全部）。
    FACTOR_RETENTION_DAYS: int = int(os.getenv("FACTOR_RETENTION_DAYS", "90"))

    # ========================================================
    # 全自動護欄 / 模式 B 自動部署（改版 Phase 4）
    # ========================================================
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
    # 常駐機會探勘間隔（分鐘）：盤中每隔幾分鐘跑一次海選、更新機會清單（Phase 10 step-02）。
    # 0 = 關掉常駐掃描。只當「首次建規則列」的種子預設，之後以 DB 的 scan_interval_min 為準。
    SCAN_INTERVAL_MIN: int = int(os.getenv("SCAN_INTERVAL_MIN", "30"))

    # ========================================================
    # 日內單一掃描迴圈（Phase 16 M8）
    # ========================================================
    # 日內 timeframe 的 Bot 不再各掛 interval job（38 bot × 各自抓 = 76+ req/min 撞限流），
    # 改由「一個掃描 job」每 N 秒批次抓全池（1 req/scan ≈ 2 req/min）再逐 bot 派發。
    # 1Day Bot 不受影響（per-bot job 保留，300s 甜蜜點不變）。0 = 關閉（日內 Bot 退回
    # per-bot job，行為與 M8 之前一致）。
    INTRADAY_SCAN_INTERVAL_SEC: int = int(os.getenv("INTRADAY_SCAN_INTERVAL_SEC", "30"))

    # ========================================================
    # 市場蒐集員 — 爬蟲收料（Phase 10 step-04）
    # ========================================================
    # 定時從 RSS / 部落格收「策略描述文字」進收件匣（raw_strategy_finds），當人 /
    # strategy-builder 寫成策略的素材。**只收料、不驗證、不部署**，收回來一律過既有 OOS 閘。
    #   - COLLECTOR_RSS_FEEDS：逗號 / 換行分隔的 RSS 網址；留空＝不收料（預設關，要收自己填）。
    #   - COLLECTOR_INTERVAL_MIN：每隔幾分鐘收一次；0＝關閉常駐收料（預設關，避免無故打外站）。
    #   - COLLECTOR_USER_AGENT：禮貌的 User-Agent，尊重來源、降低被封 IP 風險。
    COLLECTOR_RSS_FEEDS: str = os.getenv("COLLECTOR_RSS_FEEDS", "")
    COLLECTOR_INTERVAL_MIN: int = int(os.getenv("COLLECTOR_INTERVAL_MIN", "0"))
    COLLECTOR_USER_AGENT: str = os.getenv(
        "COLLECTOR_USER_AGENT",
        "AlbeeStockCollector/1.0 (+personal research bot; best-effort, respects robots)",
    )

    # ========================================================
    # 探勘橋 — raw find → LLM 產候選（Phase 12 step-02）
    # ========================================================
    # 每日定時把收件匣（raw_strategy_finds, status=new）的素材交給本機 Ollama 判讀：
    # 「這篇在講哪種**既有**策略？建議什麼參數？」有提案 → 建 StrategyKnowledge candidate
    # （之後仍要過 OOS 閘 + 人工晉升才算數）；不相關 → 標 discarded。
    # ★ LLM 只提既有策略的參數、不生成程式碼；素材不外送雲端（走 llm.py 同一道外送閘）。
    #   - DISCOVERY_ENABLED：總開關（預設 false，不掛排程、行為與沒這功能一樣）。
    #   - DISCOVERY_BATCH_SIZE：一輪最多處理幾筆素材（防 LLM 跑整夜）。
    #   - DISCOVERY_HOUR：每日幾點跑（24 小時制，預設 7 = 盤前）。
    DISCOVERY_ENABLED: bool = os.getenv("DISCOVERY_ENABLED", "false").lower() in ("1", "true", "yes")
    DISCOVERY_BATCH_SIZE: int = int(os.getenv("DISCOVERY_BATCH_SIZE", "5"))
    DISCOVERY_HOUR: int = int(os.getenv("DISCOVERY_HOUR", "7"))

    # ========================================================
    # 候選自動批次驗證 — OOS 閘排程化（Phase 12 step-03）
    # ========================================================
    # 每日定時把知識庫的 candidate 批次送進**既有** evolution.validate_candidate
    # （walk-forward OOS 閘，判準零修改）→ 自然流轉 validated / rejected，不等人逐筆按。
    # ★ 不自動晉升 curated（人在迴路鐵則）；單筆失敗不擋整批、連續 3 次才標 rejected。
    #   - AUTO_VALIDATE_ENABLED：總開關（預設 false，不掛排程、行為與沒這功能一樣）。
    #   - AUTO_VALIDATE_BATCH_SIZE：一輪最多驗幾筆（回測吃 CPU，防排程時段跑不完）。
    #   - AUTO_VALIDATE_HOUR：每日幾點跑（24 小時制，預設 8 = discovery(7) 之後）。
    #   - AUTO_VALIDATE_SYMBOL：單檔相容用標的（舊欄位保留；籃子留空時退回它）。
    #   - AUTO_VALIDATE_SYMBOLS：★驗證籃子（逗號分隔，跨產業）。單一標的樣本窄＋過擬合單檔
    #     個性；改用「大盤+科技/金融/能源/醫療/工業/零售/半導體」一籃子，每檔各跑 walk-forward
    #     → OOS EV 池化 → 同一支 is_layer_worth_it（judge 零改、只改餵料）。增刪標的＝改一行。
    #   - AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL：每檔最低交易次數門檻 X。某檔在所有 fold 的總
    #     num_round_trips < X → 整檔排除（避免靠運氣少數幾筆大賺污染池化結果）。預設 5：
    #     保守低門檻，先求「該檔真的有出手」即納入，太高會把短窗低頻策略全排除掉。
    #   - AUTO_VALIDATE_DAYS：回看天數。要夠長湊出 ≥VALIDATION_MIN_FOLDS(3) 個 walk-forward
    #     fold——365 天只 ~250 根＝1 fold，任何策略都被「樣本太少」打回（OOS 閘等於沒在評）。
    #     預設 3650 天（~10 年 ~2500 根 ~30 folds）：fold 最多、橫跨多種市況、最難過擬合。
    #     代價：單筆驗證變慢（N 檔 × ~30 folds × 回測）。實測對照：540=3、750=5、1100=9 folds。
    #     ★ 資料源前提：market_data.get_bars(source=DATA_SOURCE) 要抓得到 10 年——Alpaca 免費約
    #       2016 起（~9 年）、yfinance 全史。抓不到只會 fold 變少、不會錯（不影響判準正確性）。
    AUTO_VALIDATE_ENABLED: bool = os.getenv("AUTO_VALIDATE_ENABLED", "false").lower() in ("1", "true", "yes")
    AUTO_VALIDATE_BATCH_SIZE: int = int(os.getenv("AUTO_VALIDATE_BATCH_SIZE", "3"))
    AUTO_VALIDATE_HOUR: int = int(os.getenv("AUTO_VALIDATE_HOUR", "8"))
    AUTO_VALIDATE_SYMBOL: str = os.getenv("AUTO_VALIDATE_SYMBOL", "SPY")
    AUTO_VALIDATE_SYMBOLS: str = os.getenv(
        "AUTO_VALIDATE_SYMBOLS",
        # 跨產業 38 檔籃子（跳過醫療/零售）：大盤指數 5、半導體 10、能源 3、科技 10、
        # 金融 5、工業 5。籃子越寬越難過擬合單檔個性；各檔跑 walk-forward → OOS EV 池化
        # （evolution._validate_basket）。增刪標的＝改這一行（或用 .env 覆寫）。
        "SPY,QQQ,DIA,IWM,VTI,"                                  # 大盤指數 5
        "NVDA,AMD,AVGO,TSM,INTC,QCOM,MU,AMAT,LRCX,ASML,"        # 半導體 10
        "XOM,CVX,COP,"                                          # 能源 3
        "AAPL,MSFT,GOOGL,AMZN,META,TSLA,NFLX,ADBE,CRM,ORCL,"    # 科技 10
        "JPM,BAC,WFC,GS,MS,"                                    # 金融 5
        "CAT,BA,HON,UNP,GE",                                    # 工業 5
    )
    AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL: int = int(
        os.getenv("AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL", "5")
    )
    AUTO_VALIDATE_DAYS: int = int(os.getenv("AUTO_VALIDATE_DAYS", "3650"))

    @property
    def auto_validate_symbols(self) -> list[str]:
        """
        驗證籃子（拆 AUTO_VALIDATE_SYMBOLS 逗號字串）→ 去空白、去重、轉大寫的清單。
        留空或全空白時退回 [AUTO_VALIDATE_SYMBOL]（單檔相容，不破壞舊行為）。
        """
        raw = [s.strip().upper() for s in (self.AUTO_VALIDATE_SYMBOLS or "").split(",")]
        symbols: list[str] = []
        for s in raw:
            if s and s not in symbols:  # 去空白、去重、保序
                symbols.append(s)
        return symbols or [self.AUTO_VALIDATE_SYMBOL.upper()]

    # ========================================================
    # 知識庫策略 → 自動建 Paper Bot（curated→bot 自動部署排程）
    # ========================================================
    # 把「驗證過的好策略」自動部署成 Paper Bot 掛網跑（補上 curated 知識庫接不到 Bot 的斷層，
    # 取代手動 deploy）。★只建 paper bot、不碰真錢雙閘；上真錢仍須 ALPACA_BASE_URL 實盤 +
    # ALLOW_LIVE_TRADING=true，由 alpaca_client.submit_market_order 把關。
    #   - AUTO_DEPLOY_KNOWLEDGE_ENABLED：總開關（預設 false，不掛排程、與沒這功能一樣）。
    #   - AUTO_DEPLOY_FROM_STATUS：從哪個狀態觸發。curated（預設，保留「validated→人晉升」人工閘，
    #     最安全）或 validated（全自動、少一道人把關；paper 不燒真錢）。
    #   - AUTO_DEPLOY_KNOWLEDGE_SYMBOLS：部署到哪些標的（knowledge 不綁標的，部署時才指定）。
    #   - AUTO_DEPLOY_KNOWLEDGE_HOUR：每日幾點跑（建議排在 auto_validate 之後，吃到當天剛驗過的）。
    #   - AUTO_DEPLOY_KNOWLEDGE_TRADE_AMOUNT：每個 Bot 下單金額（美元）。
    #   - AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN：一輪最多部署幾筆知識（防一次建爆 Bot）。
    #   - AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL：自動建的艦隊每幾秒輪檢一次行情。每筆知識
    #     部署到全部標的（N 檔各一個 Bot），好策略一多艦隊就大（5 策略 × 38 檔 = 190 Bot）。
    #     190 Bot × 60 秒 ≈ 3.2 req/s，逼近 Alpaca 免費 200/min；拉長到 300 秒壓到 ~0.6 req/s，
    #     省 CPU 與 API 額度。手動 deploy（人按）仍用既有 60 秒預設，不受此值影響。
    AUTO_DEPLOY_KNOWLEDGE_ENABLED: bool = os.getenv("AUTO_DEPLOY_KNOWLEDGE_ENABLED", "false").lower() in ("1", "true", "yes")
    AUTO_DEPLOY_FROM_STATUS: str = os.getenv("AUTO_DEPLOY_FROM_STATUS", "curated")
    AUTO_DEPLOY_KNOWLEDGE_SYMBOLS: str = os.getenv("AUTO_DEPLOY_KNOWLEDGE_SYMBOLS", "SPY,QQQ,AAPL")
    AUTO_DEPLOY_KNOWLEDGE_HOUR: int = int(os.getenv("AUTO_DEPLOY_KNOWLEDGE_HOUR", "9"))
    AUTO_DEPLOY_KNOWLEDGE_TRADE_AMOUNT: float = float(os.getenv("AUTO_DEPLOY_KNOWLEDGE_TRADE_AMOUNT", "1000"))
    AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN: int = int(os.getenv("AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN", "3"))
    AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL: int = int(os.getenv("AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL", "300"))

    @property
    def auto_deploy_knowledge_symbols(self) -> list[str]:
        """部署標的清單（拆 AUTO_DEPLOY_KNOWLEDGE_SYMBOLS）→ 去空白/去重/大寫。空＝空清單。"""
        raw = [s.strip().upper() for s in (self.AUTO_DEPLOY_KNOWLEDGE_SYMBOLS or "").split(",")]
        out: list[str] = []
        for s in raw:
            if s and s not in out:
                out.append(s)
        return out

    # ========================================================
    # bot 汰弱審查員（fleet 績效考核 + 軟汰弱 + 哪股票配哪策略 fit 註冊）
    # ========================================================
    # 自動部署讓 Bot 數 ＝ 好策略數 × 標的數，會持續長（5 策略 × 38 檔 = 190 Bot）。
    # 審查員每日定時：①算每支 paper Bot 實跑績效（performance.compute_bot_stats）→
    # ②把「(策略, 標的) → 績效 + 評等」upsert 進 strategy_symbol_fit 註冊表（哪股票配哪策略）→
    # ③實跑夠久夠多筆但不及格的 Bot「軟汰弱」（is_active=False + culled_at，不刪資料）。
    # ★ 只碰 promotion_status="paper"；proposed_live/approved_live（真錢相關）一律不動。
    #   - BOT_REVIEW_ENABLED：總開關（預設 false，不掛排程、與沒這功能一樣）。
    #   - BOT_REVIEW_HOUR：每日幾點跑（排在 auto_deploy_knowledge(9) 之後，先建 Bot 再有得審）。
    #   - BOT_REVIEW_MIN_ROUND_TRIPS：判生死的最低完整買賣次數。低於此＝樣本不足，續觀察不汰。
    #   - BOT_REVIEW_MIN_AGE_DAYS：建立後給的觀察寬限天數。沒滿這天數不汰（給新 Bot 時間表現）。
    #   - BOT_REVIEW_CULL_WINRATE / CULL_RETURN_PCT / CULL_MAX_DD：汰弱門檻——夠久夠多筆後，
    #     勝率 < CULL_WINRATE 或 報酬率 < CULL_RETURN_PCT 或 最大回撤 > CULL_MAX_DD 任一中 → 汰。
    #   - BOT_REVIEW_GOOD_WINRATE：評「good」的勝率門檻（且報酬率為正）；good/poor 寫進 fit 表。
    #   - BOT_REVIEW_MAX_CULL_PER_RUN：一輪最多汰幾支（防門檻設錯一次誤殺整片艦隊）。
    BOT_REVIEW_ENABLED: bool = os.getenv("BOT_REVIEW_ENABLED", "false").lower() in ("1", "true", "yes")
    BOT_REVIEW_HOUR: int = int(os.getenv("BOT_REVIEW_HOUR", "11"))
    BOT_REVIEW_MIN_ROUND_TRIPS: int = int(os.getenv("BOT_REVIEW_MIN_ROUND_TRIPS", "10"))
    BOT_REVIEW_MIN_AGE_DAYS: int = int(os.getenv("BOT_REVIEW_MIN_AGE_DAYS", "14"))
    BOT_REVIEW_CULL_WINRATE: float = float(os.getenv("BOT_REVIEW_CULL_WINRATE", "40"))
    BOT_REVIEW_CULL_RETURN_PCT: float = float(os.getenv("BOT_REVIEW_CULL_RETURN_PCT", "0"))
    BOT_REVIEW_CULL_MAX_DD: float = float(os.getenv("BOT_REVIEW_CULL_MAX_DD", "35"))
    BOT_REVIEW_GOOD_WINRATE: float = float(os.getenv("BOT_REVIEW_GOOD_WINRATE", "55"))
    BOT_REVIEW_MAX_CULL_PER_RUN: int = int(os.getenv("BOT_REVIEW_MAX_CULL_PER_RUN", "20"))

    # ========================================================
    # AI 每日交易事後檢討（trade_review）
    # ========================================================
    # 每天美股收盤後（UTC 20:00 = ET 16:00）自動觸發，讀取當日決策 → LLM 分析 → 寫 explorations/ → 推播。
    #   - TRADE_REVIEW_ENABLED：總開關（預設開）。
    #   - TRADE_REVIEW_HOUR：每日幾點跑（UTC；預設 20 = ET 16:00 收盤後）。
    TRADE_REVIEW_ENABLED: bool = os.getenv("TRADE_REVIEW_ENABLED", "true").lower() in ("1", "true", "yes")
    TRADE_REVIEW_HOUR: int = int(os.getenv("TRADE_REVIEW_HOUR", "20"))

    # ========================================================
    # 策略進化反饋迴圈（strategy_feedback）
    # ========================================================
    # Bot 被汰弱或降級後，自動分析失敗原因、由 LLM 提案新參數候選寫入知識庫。
    #   - FEEDBACK_MIN_RATIO：實跑均值 / OOS 期望值 < 此比值才觸發（預設 0.6 = 低於 OOS 的 60%）。
    #   - FEEDBACK_MIN_ROUND_TRIPS：觸發所需的最低完整買賣回合數（預設 5）。
    #   - FEEDBACK_THESIS_LIMIT：傳給 LLM 分析的最近失敗案例數（預設 10）。
    FEEDBACK_MIN_RATIO: float = float(os.getenv("FEEDBACK_MIN_RATIO", "0.6"))
    FEEDBACK_MIN_ROUND_TRIPS: int = int(os.getenv("FEEDBACK_MIN_ROUND_TRIPS", "5"))
    FEEDBACK_THESIS_LIMIT: int = int(os.getenv("FEEDBACK_THESIS_LIMIT", "10"))

    # ========================================================
    # 開機補跑（catch-up on boot）— 維運安全軌
    # ========================================================
    # 家用電腦不是 24/7：每日 cron 時刻沒開機，那天管線整段跳過。
    # 開機補跑 = 後端啟動時把「開關有開 + 時刻已過 + 今天還沒跑」的每日 job 立刻補跑。
    # 只解決「時間到沒開機」，不放大權限：各 job 自己的 enable 閘照常生效。
    CATCHUP_ON_BOOT: bool = os.getenv("CATCHUP_ON_BOOT", "true").lower() in ("1", "true", "yes")

    # ========================================================
    # 每日領導股回測紀錄（daily leader backtest）
    # ========================================================
    # 每天對主要領導股各跑一輪全自動掃描（OOS EV 排名），各檔冠軍存一筆 BacktestRun，
    # 日積月累成「領導股最佳策略 EV 時間序列」。只落紀錄、不下單、不建 Bot。
    #   - LEADER_BACKTEST_ENABLED：總開關（預設開——純本機回測紀錄，無對外動作）。
    #   - LEADER_BACKTEST_SYMBOLS：逗號分隔的上市領導股清單（未上市公司回不了測，
    #     交給 collector 的 PRIVATE_WATCH_KEYWORDS 監控）。
    #   - LEADER_BACKTEST_DAYS：每輪回測往前抓幾天。
    #   - LEADER_BACKTEST_HOUR：每日幾點跑（24 小時制；排在其他每日 job 之後，避免擠 CPU）。
    LEADER_BACKTEST_ENABLED: bool = os.getenv("LEADER_BACKTEST_ENABLED", "true").lower() in ("1", "true", "yes")
    LEADER_BACKTEST_SYMBOLS: str = os.getenv(
        "LEADER_BACKTEST_SYMBOLS",
        "AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA",
    )
    LEADER_BACKTEST_DAYS: int = int(os.getenv("LEADER_BACKTEST_DAYS", "365"))
    LEADER_BACKTEST_HOUR: int = int(os.getenv("LEADER_BACKTEST_HOUR", "10"))

    # ========================================================
    # 未上市公司關鍵字監控（collector 加掛）
    # ========================================================
    # SpaceX 這類未上市公司沒有 K 線、回不了測——只能「監控記錄」：
    # collector 收料時比對關鍵字，命中的素材打上 watch:<關鍵字> 標籤留檔 + 通知提及。
    # 逗號分隔、不分大小寫；留空 = 關閉監控。
    PRIVATE_WATCH_KEYWORDS: str = os.getenv("PRIVATE_WATCH_KEYWORDS", "SpaceX")

    # ========================================================
    # 政治專討員 — Discord 事件流（Phase 10 step-05）
    # ========================================================
    # 從 Discord 頻道偵測政治貼文（例如川普發文鏡像）→ 本機 Ollama 判讀 → 接既有風險煞車。
    # ★ 定位是「煞車（降風險、不開新倉），不是油門」。預設**完全關閉**，不影響現行下單。
    #   - POLITICAL_ENABLED：bridge 總開關（預設 false）。false＝political_size_factor 一律放行。
    #   - POLITICAL_DISCORD_TOKEN / POLITICAL_CHANNEL_ID：Discord runner 用（留空＝不啟動 runner）。
    #   - POLITICAL_AUTHOR_FILTER：只處理這個作者名的貼文（留空＝該頻道所有貼文）。
    #   - POLITICAL_EVENT_MAX_AGE_HOURS：政治情緒超過幾小時就退場、不再煞車（預設 24h）。
    #   - POLITICAL_BACKFILL_LIMIT：runner 啟動時「DB 空表」才用的保底回補筆數。
    #     正常情況回補走「時間型補齊」（只補比 DB 既有最新貼文更新的），空表時退回
    #     只補最近 N 筆且不發通知，避免剛搬 DB 瞬間補爆（0＝關閉回補，預設 30）。
    #   - POLITICAL_ALERT_COOLDOWN_MIN：同一作者的政治風險警報節流分鐘數（防來源倒貨 /
    #     重判洗版；冷卻期內同作者只發一則，其餘只印 console，預設 10）。
    POLITICAL_ENABLED: bool = os.getenv("POLITICAL_ENABLED", "false").lower() in ("1", "true", "yes")
    POLITICAL_DISCORD_TOKEN: str = os.getenv("POLITICAL_DISCORD_TOKEN", "")
    POLITICAL_CHANNEL_ID: str = os.getenv("POLITICAL_CHANNEL_ID", "")
    POLITICAL_AUTHOR_FILTER: str = os.getenv("POLITICAL_AUTHOR_FILTER", "")
    POLITICAL_EVENT_MAX_AGE_HOURS: float = float(os.getenv("POLITICAL_EVENT_MAX_AGE_HOURS", "24"))
    POLITICAL_BACKFILL_LIMIT: int = int(os.getenv("POLITICAL_BACKFILL_LIMIT", "30"))
    POLITICAL_ALERT_COOLDOWN_MIN: int = int(os.getenv("POLITICAL_ALERT_COOLDOWN_MIN", "10"))

    # ========================================================
    # 回測成本模型（Phase 6 step-02）
    # ========================================================
    # 讓回測吃到真實摩擦成本，EV 才誠實（沒成本的 EV 是行銷數字，不是可下注的數字）。
    # 單位都是 basis point（bps，萬分之一）：5 bps = 0.05%。
    #   - 手續費：Alpaca 美股免佣，預設 0；保留欄位讓未來換券商 / 標的能調。
    #   - 滑價：市價單實際成交價會比看到的價差一點（含半個買賣價差），預設 5 bps 保守估。
    # 買進成交價 ×(1+slippage)、賣出 ×(1−slippage)，買賣再各扣 commission。
    BACKTEST_COMMISSION_BPS: float = float(os.getenv("BACKTEST_COMMISSION_BPS", "0"))
    BACKTEST_SLIPPAGE_BPS: float = float(os.getenv("BACKTEST_SLIPPAGE_BPS", "5"))

    # ========================================================
    # 樣本外驗證（Phase 6 step-04）
    # ========================================================
    # optimizer 海選挑冠軍時，把歷史切「訓練段 / 測試段」，冠軍看「測試段（樣本外 OOS）」的 EV，
    # 不看樣本內——避免挑到「最會擬合過去雜訊」的參數。test_ratio = 測試段佔比（時間軸後段）。
    OOS_TEST_RATIO: float = float(os.getenv("OOS_TEST_RATIO", "0.3"))

    # M3：optimizer 排名守門（walk-forward 聚合 OOS 之後的硬約束）
    # - MIN_OOS_TRIPS：OOS 交易樣本數低於此值的組合直接沉底（1~2 筆的「冠軍」是噪音，
    #   stock_pool 體檢已用 38 檔驗證過這個教訓）。
    # - MAX_OVERFIT_GAP：過擬合差距 (IS−OOS)/|IS| 超過此值的組合沉底
    #   （0.5 = 樣本外掉超過一半，樣本內再漂亮也不可信）。
    OPTIMIZER_MIN_OOS_TRIPS: int = int(os.getenv("OPTIMIZER_MIN_OOS_TRIPS", "20"))
    OPTIMIZER_MAX_OVERFIT_GAP: float = float(os.getenv("OPTIMIZER_MAX_OVERFIT_GAP", "0.5"))

    # ========================================================
    # AI 情緒閘（Phase 6 step-07）
    # ========================================================
    # 讓第二層 LLM 算出的情緒分數「真正影響部署決策」，但守住「EV 為主、情緒為輔」：
    # 情緒只能否決（bearish / 分數過低）或當次要排序加權，不能蓋過期望值。
    #   - SENTIMENT_GATING：總開關（預設開）。關掉 = 完全退回純 EV 行為（向後相容）。
    #   - SENTIMENT_MIN_SCORE：情緒分數低於此值視為「情緒否決」（不進自動部署）。
    # 沒跑情緒（LLM 沒設定 / 被外送閘擋下，sentiment=None）一律視為中性、不否決（best-effort）。
    SENTIMENT_GATING: bool = os.getenv("SENTIMENT_GATING", "true").lower() in ("1", "true", "yes")
    SENTIMENT_MIN_SCORE: float = float(os.getenv("SENTIMENT_MIN_SCORE", "-20"))

    # ========================================================
    # 組合層風控（Phase 6 step-05 資金守門 / step-09 回撤熔斷）
    # ========================================================
    # 資金守門（step-05）：建 Bot / 下買單前，先確認帳戶付得起，且永遠保留一筆現金緩衝。
    # 可動用額度 = available_cash ×(1 − reserve_ratio)。預設保留 20% 現金。
    PORTFOLIO_CASH_RESERVE_RATIO: float = float(os.getenv("PORTFOLIO_CASH_RESERVE_RATIO", "0.2"))
    # 回撤熔斷（step-09）：總權益從峰值回落超過此百分比 → 暫停所有新增曝險（新買進 + 自動部署），
    # 但既有持倉的風控出場照常運作。預設 20（%）。
    PORTFOLIO_MAX_DRAWDOWN_PCT: float = float(os.getenv("PORTFOLIO_MAX_DRAWDOWN_PCT", "20"))

    # ========================================================
    # 市場狀態分類器（Phase 7 step-02 / step-03）
    # ========================================================
    # 把 regime_features 的數字特徵，用「規則式決策樹（路線 A，純 if-else）」分成幾種
    # 有名字的市場狀態。閾值放這裡（好調、好測），不寫死在程式裡。
    #   - HIGH_VOL：近 20 日年化波動 ≥ 此值 → 高波動（混亂，優先別追）。0.50 = 50%。
    #   - VOLUME_SPIKE + FLAT_RETURN：量比 ≥ VOLUME_SPIKE 且 |近5日報酬| ≤ FLAT_RETURN
    #     → 爆量滯漲（量價背離，你舉的「量大卻沒漲幅」）。
    #   - ADX_TREND：趨勢強度(ADX) ≥ 此值 → 趨勢盤；都不符就歸「盤整」。
    REGIME_HIGH_VOL_THRESHOLD: float = float(os.getenv("REGIME_HIGH_VOL_THRESHOLD", "0.50"))
    REGIME_VOLUME_SPIKE: float = float(os.getenv("REGIME_VOLUME_SPIKE", "2.0"))
    REGIME_FLAT_RETURN: float = float(os.getenv("REGIME_FLAT_RETURN", "0.02"))
    REGIME_ADX_TREND: float = float(os.getenv("REGIME_ADX_TREND", "25.0"))
    # step-03 自適應選策略：某狀態的子樣本交易筆數 < 此門檻，就不信任該狀態的統計，
    # 退回保守預設（不亂下注）。切子樣本後筆數會驟減，這道門檻防「12 筆勝率 75% 是運氣」。
    REGIME_MIN_SAMPLE: int = int(os.getenv("REGIME_MIN_SAMPLE", "10"))
    # step-03 對照表 / 自適應實盤的回看窗口（天）。實盤抓這麼多天算特徵 + 挑策略，
    # 與對照表建立時同窗口，特徵才一致（呼應「回測 = 實盤」鐵則）。
    REGIME_MAP_DAYS: int = int(os.getenv("REGIME_MAP_DAYS", "365"))

    # ========================================================
    # 防過擬合驗證框架（Phase 7 step-07，橫跨全部的鐵律）
    # ========================================================
    # 讓「狀態分類 / 自適應選策略 / meta-labeling」等加上去的層，都必須在真正的樣本外
    # 證明自己有加分，否則砍掉。視窗單位都是「K 棒數（bars）」，不是日曆天。
    #   - TRAIN_WINDOW：每個 fold 之前要保留多少根當訓練 / 暖機（滾動前進的步距基準）。
    #   - TEST_WINDOW：每個 fold 的樣本外測試長度。
    #   - STEP：視窗每次往前滾幾根（= TEST_WINDOW 則 fold 不重疊）。
    VALIDATION_TRAIN_WINDOW: int = int(os.getenv("VALIDATION_TRAIN_WINDOW", "180"))
    VALIDATION_TEST_WINDOW: int = int(os.getenv("VALIDATION_TEST_WINDOW", "60"))
    VALIDATION_STEP: int = int(os.getenv("VALIDATION_STEP", "60"))
    # purged K-Fold（給學習式模型用）：折數 + embargo（測試段前後各清掉幾根，防交界洩漏未來）。
    VALIDATION_KFOLD: int = int(os.getenv("VALIDATION_KFOLD", "5"))
    VALIDATION_EMBARGO: int = int(os.getenv("VALIDATION_EMBARGO", "5"))
    # 「這層值不值得上線」判定：候選的 OOS EV 平均需贏 baseline 至少這麼多（金額），
    # 且至少要有這麼多個 fold 才採信（樣本太少不算數）。門檻預設 0＝只要不比 baseline 差就算數，
    # 但仍要求 fold 數達標；想更嚴格就把門檻調正。
    VALIDATION_MIN_IMPROVEMENT: float = float(os.getenv("VALIDATION_MIN_IMPROVEMENT", "0"))
    VALIDATION_MIN_FOLDS: int = int(os.getenv("VALIDATION_MIN_FOLDS", "3"))

    # ========================================================
    # 分數凱利部位（Phase 7 step-04）
    # ========================================================
    # 用「OOS 勝率 + OOS 賠率」算該下注本金的多少 %，取代寫死的固定 trade_amount。
    # 凱利對輸入估計極敏感，所以三重保守：用 OOS 數字、只取分數凱利、再用硬上限夾住。
    #   - KELLY_FRACTION：分數凱利係數（只取 f* 的這個比例；0.25 = ¼ 凱利，實務常用）。
    #   - KELLY_MAX_FRACTION：單檔部位硬上限（占可用資金比例），防估計偏高導致暴衝。
    #   - KELLY_MIN_ROUND_TRIPS：OOS 完整買賣回合數低於此值 → W/R 不可信，回 0（不下注）。
    KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.25"))
    KELLY_MAX_FRACTION: float = float(os.getenv("KELLY_MAX_FRACTION", "0.2"))
    KELLY_MIN_ROUND_TRIPS: int = int(os.getenv("KELLY_MIN_ROUND_TRIPS", "10"))

    # ========================================================
    # meta-labeling 二級過濾（Phase 7 step-05）
    # ========================================================
    # 一級模型（策略 + step-03 選擇器）決定「方向」；二級（這層）只決定「這次該不該下注」。
    # 起步用規則式（零過擬合、可解釋）：用 step-02 狀態 + step-01 特徵過濾低品質進場訊號。
    #   - META_LABEL_ENABLED：總開關（預設開）。關掉 = 完全退回純一級訊號（向後相容）。
    #   - META_MIN_CONFIDENCE：二級信心低於此值 → 否決該進場訊號（不下注）。
    META_LABEL_ENABLED: bool = os.getenv("META_LABEL_ENABLED", "true").lower() in ("1", "true", "yes")
    META_MIN_CONFIDENCE: float = float(os.getenv("META_MIN_CONFIDENCE", "0.5"))

    # ========================================================
    # 事件驅動風險閘（Phase 7 step-06，情緒當煞車、不當油門）
    # ========================================================
    # 重大負面情緒/事件 → 降風險（不開新倉 / 縮部位），**不據此猜方向重壓**。
    # bearish / 分數低於 SENTIMENT_MIN_SCORE 仍由情緒閘（step-07/Phase6 step-07）直接否決；
    # 這裡補「不到否決、但偏謹慎」的中間帶：縮小部位而非全砍。best-effort，連不上不阻斷。
    #   - EVENT_RISK_ENABLED：總開關（預設開）。關掉 = 不縮部位（向後相容）。
    #   - EVENT_RISK_CAUTION_SCORE：情緒分數低於此值（但未達否決）→ 進謹慎帶、縮部位。
    #   - EVENT_RISK_SIZE_FACTOR：謹慎帶的部位縮放係數（0.5 = 砍半）。
    EVENT_RISK_ENABLED: bool = os.getenv("EVENT_RISK_ENABLED", "true").lower() in ("1", "true", "yes")
    EVENT_RISK_CAUTION_SCORE: float = float(os.getenv("EVENT_RISK_CAUTION_SCORE", "0"))
    EVENT_RISK_SIZE_FACTOR: float = float(os.getenv("EVENT_RISK_SIZE_FACTOR", "0.5"))

    # ========================================================
    # 券商端止損託管（維運安全軌 H1）
    # ========================================================
    # 開啟時：Bot 進場成交後，把止損「託管」到券商端（Alpaca GTC stop / trailing stop 單），
    # 電腦當機 / 斷網 / 重開機期間止損照樣執行（本機輪詢保留當備援）。
    # 代價：Alpaca 的 stop 單只支援整股 → 掛保護單的 Bot 進場股數會取整（floor），
    # trade_amount 買不起 1 股的高價股會跳過進場（記決策審計）。
    # 預設開（這是「真錢前必備」的安全軌）；關掉 = 完全退回純本機輪詢（向後相容）。
    BROKER_STOP_ENABLED: bool = os.getenv("BROKER_STOP_ENABLED", "true").lower() in ("1", "true", "yes")

    # ========================================================
    # tracking error 對帳 + 自動降級（維運安全軌 H3）
    # ========================================================
    # 每日比對「回測 OOS 期望值（% of 本金）vs Paper 實跑每回合報酬率（%）」。
    # 實跑連續低於「OOS × 折扣」→ 自動停 Bot + 通知（不平倉、不撤券商端保護單，人再決定）。
    # 這是「有晉升、沒降級」的補完——上線後唯一的品管。
    #   - TRACKING_MIN_ROUND_TRIPS：Paper 完整回合數低於此值不對帳（樣本太少不冤殺）。
    #   - TRACKING_WINDOW：取最近幾回合的平均報酬率來比（滾動窗）。
    #   - TRACKING_DEMOTE_RATIO：門檻 = OOS expectancy × 此折扣（0.5 = 實跑掉到一半就算違規）。
    #   - TRACKING_DEMOTE_AFTER：連續違規幾次才降級（只在有新回合的日子計數，寧鈍勿敏）。
    #   - TRACKING_CHECK_HOUR：每日對帳的本機時刻（建議美股收盤後）。
    TRACKING_MIN_ROUND_TRIPS: int = int(os.getenv("TRACKING_MIN_ROUND_TRIPS", "5"))
    TRACKING_WINDOW: int = int(os.getenv("TRACKING_WINDOW", "10"))
    TRACKING_DEMOTE_RATIO: float = float(os.getenv("TRACKING_DEMOTE_RATIO", "0.5"))
    TRACKING_DEMOTE_AFTER: int = int(os.getenv("TRACKING_DEMOTE_AFTER", "3"))
    TRACKING_CHECK_HOUR: int = int(os.getenv("TRACKING_CHECK_HOUR", "9"))

    # ========================================================
    # 心跳 + dead-man switch（維運安全軌 H2）
    # ========================================================
    # 一人公司沒有同事盯系統：每日心跳日報（給人看）+ 對外側監測服務 ping（給機器看）。
    # 警報必須在「系統外側」——本機死了，本機發不出「我死了」的通知。
    #   - HEARTBEAT_PING_URL：healthchecks.io 的專屬 ping 網址。留空＝dead-man 功能關。
    #   - HEARTBEAT_HOUR：每日心跳日報的本機時刻（24 小時制的「時」）。
    #   - HEARTBEAT_PING_INTERVAL_MIN：每隔幾分鐘 ping 外側一次（外側 check 的 period
    #     建議設 1 小時 + grace 1 小時 → 系統死超過約 2 小時必有警報）。
    HEARTBEAT_PING_URL: str = os.getenv("HEARTBEAT_PING_URL", "")
    HEARTBEAT_HOUR: int = int(os.getenv("HEARTBEAT_HOUR", "8"))
    HEARTBEAT_PING_INTERVAL_MIN: int = int(os.getenv("HEARTBEAT_PING_INTERVAL_MIN", "30"))

    # ========================================================
    # 即時報價推送（改版子軌：AI 終端機改版，非主線 Phase 6）
    # ========================================================
    # 後端每隔幾秒向 Alpaca 拉一次最新成交價，再透過 WebSocket 推給前端。
    # 數字越小越即時、但越耗 Alpaca 的 REST 額度；5 秒對學習/觀察很夠用。
    QUOTE_POLL_INTERVAL_SEC: float = float(os.getenv("QUOTE_POLL_INTERVAL_SEC", "5"))

    # ========================================================
    # Agent Gateway — 外部 AI agent 受限存取（採納自 QuantDinger）
    # ========================================================
    # 讓 Claude / Cursor 等外部 AI 透過 /api/agent/v1/* 驅動我們的回測 / 策略 / 知識庫查詢，
    # 並可下「預設 paper」的單。沿用實盤雙閘的精神，再加一道 agent 專屬閘：
    #   - AGENT_API_TOKEN：bearer 驗證用的密鑰。留空＝整個 Gateway 關閉（端點一律回 503）。
    #     ★ 絕不 commit，只放 .env；自己用 `python -c "import secrets;print(secrets.token_urlsafe(32))"` 產一把。
    #   - AGENT_LIVE_TRADING_ENABLED：agent 下單能否碰真錢的「第三道閘」（鏡像 ALLOW_LIVE_TRADING）。
    #     預設 false＝agent 只能下 paper 單。要 agent 動真錢須三者齊開：實盤網址 + ALLOW_LIVE_TRADING
    #     + 本閘，且仍由 alpaca_client.submit_market_order 的雙閘把關（本閘只是再多一層拒絕）。
    AGENT_API_TOKEN: str = os.getenv("AGENT_API_TOKEN", "")
    AGENT_LIVE_TRADING_ENABLED: bool = os.getenv("AGENT_LIVE_TRADING_ENABLED", "false").lower() in ("1", "true", "yes")

    # ========================================================
    # 探討（檢討）檔案記憶（Phase 5）
    # ========================================================
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
