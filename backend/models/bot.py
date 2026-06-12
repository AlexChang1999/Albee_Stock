"""
Bot 資料模型
============
一個 Bot = 一個獨立運行的交易策略設定。

例如：
- 「AAPL 均線交叉 Bot」：用均線交叉策略，盯著蘋果股票
- 「TSLA RSI Bot」：用 RSI 策略，盯著特斯拉

每個 Bot 都是資料庫裡的一筆紀錄。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON

from backend.database import Base


class Bot(Base):
    __tablename__ = "bots"  # 資料表名稱

    id = Column(Integer, primary_key=True, index=True)

    # Bot 的名稱，方便辨識，例如 "AAPL 均線交叉"
    name = Column(String, nullable=False)

    # 用哪一種策略，對應 strategies/ 裡的策略代號，例如 "ma_crossover"
    strategy = Column(String, nullable=False)

    # 交易標的（股票代號），例如 "AAPL"
    symbol = Column(String, nullable=False)

    # 策略參數，用 JSON 存（不同策略需要的參數不同）
    # 例如均線交叉：{"short_window": 5, "long_window": 20}
    params = Column(JSON, default=dict)

    # 每次下單金額（美元），新手先用固定金額控制風險
    trade_amount = Column(Float, default=1000.0)

    # ----- 風控（Phase 4 監聽系統用）-----
    # 以下三個百分比皆「可不填」(None)；填了才啟用該機制。
    # 用小數表示，例如 0.10 = 10%。

    # 固定止盈：現價漲到「進場價 ×(1+此值)」就全部賣出。例：0.10 = +10% 出場
    take_profit_pct = Column(Float, nullable=True)

    # 固定止損：現價跌到「進場價 ×(1−此值)」就全部賣出。例：0.05 = −5% 出場
    stop_loss_pct = Column(Float, nullable=True)

    # 追蹤止損：從「持倉期間最高價」回落此比例就賣出。例：0.03 = 回落 3% 出場
    # 跟固定止損的差別：止損點會隨價格創新高而往上抬，鎖住已賺到的獲利
    trailing_stop_pct = Column(Float, nullable=True)

    # 監測頻率（秒）：啟動後每隔幾秒檢查一次行情。預設 60 秒
    check_interval_sec = Column(Integer, default=60)

    # 持倉期間出現過的最高價（給「追蹤止損」用，內部狀態非使用者設定）。
    # None = 目前空手或尚未進場。進場時設為進場價、每次檢查更新、平倉/空手時清回 None。
    # 為何存進資料庫而非記憶體：後端重啟後追蹤止損才不會把最高價歸零、保護中斷一段時間。
    peak_price = Column(Float, nullable=True)

    # 券商端保護單 id（維運安全軌 H1，內部狀態非使用者設定）。
    # 進場後掛在 Alpaca 的 GTC stop / trailing stop 單的訂單 id；None = 沒掛。
    # 存 DB 的理由同 peak_price：後端重啟後才知道券商端還掛著哪張保護單，
    # 不會重複掛單、也能在它成交後回填交易紀錄。
    protective_order_id = Column(String, nullable=True)

    # 自適應模式（Phase 7 step-03）：開啟時不固定用 strategy 欄位的策略，
    # 而是每輪先算當下「市場狀態」，查「狀態→最佳策略對照表」挑策略。
    # 預設關（False）＝沿用固定策略，向後相容。狀態無可信策略時保守觀望（不亂下注）。
    adaptive = Column(Boolean, nullable=False, default=False)

    # Bot 是否啟用中
    is_active = Column(Boolean, default=False)

    # 最後一次成功跑完監測檢查的時間（None = 還沒跑過）。
    # 前端用它顯示「最後檢查：X 秒前」，確認排程真的在動。
    last_checked_at = Column(DateTime, nullable=True)

    # 建立時間
    created_at = Column(DateTime, default=datetime.now)

    # ----- 董事會晉升狀態（Phase 10 step-06，人在迴路）-----
    # Bot 從 Paper（模擬）晉升到真錢的人工核准軌跡。預設 "paper"。
    #   paper          ：跑模擬中（預設）
    #   proposed_live  ：系統/人提議「建議上真錢」，待老闆核准
    #   approved_live  ：老闆已核准（★只是「人已同意」的旗標，不放行真錢！）
    #   rejected       ：老闆退回
    # ★安全紅線：approved_live 不等於送真錢。真錢仍須 ALPACA_BASE_URL 實盤 +
    #   ALLOW_LIVE_TRADING=true 雙閘，由 alpaca_client.submit_market_order 把關（兩者 AND）。
    promotion_status = Column(String, nullable=False, default="paper")

    # 被提議上真錢的時間（None = 還沒被提議）
    promotion_proposed_at = Column(DateTime, nullable=True)

    # 提議達標證據摘要 / 退回理由（人看的一句話，詳細軌跡另寫 explorations 記憶）
    promotion_reason = Column(String, nullable=True)

    # ----- tracking error 自動降級（維運安全軌 H3）-----
    # 「回測 OOS 期望值 vs Paper 實跑」每日對帳：實跑連續低於門檻 → 自動停 Bot（人再決定）。
    # 降級只停新決策，不平倉、不撤券商端保護單；單向不自動恢復（重啟走既有 /bots/{id}/start）。

    # 連續違規次數（每日對帳：違規 +1、回到門檻上歸零；達 TRACKING_DEMOTE_AFTER 即降級）
    tracking_breach_count = Column(Integer, nullable=False, default=0)

    # 上次對帳時的完整回合數——回合數沒增加就跳過不計數，防同一批樣本連日重複扣分
    tracking_last_rt_count = Column(Integer, nullable=False, default=0)

    # 被自動降級的時間 / 原因（None = 沒被降級過；給前端與審計看）
    demoted_at = Column(DateTime, nullable=True)
    demote_reason = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Bot {self.id} {self.name} ({self.strategy} on {self.symbol})>"
