"""
決策審計軌跡資料模型（Phase 6 step-08）
========================================
每一次 Bot 檢查都留下「為何在這個時點買 / 賣 / 不動」的持久紀錄。

跟 TradeLog 的差別：
- TradeLog 只在「真的成交」時才寫。
- DecisionLog 連「沒成交但有決策」的時點都寫——觀望、續抱、休市跳過、購買力不足、熔斷。
自動跑真錢的系統必須能事後查驗每個決定（「昨天 10:35 為什麼沒進場？」），
這份紀錄也是日後餵 LLM 做檢討的素材。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON

from backend.database import Base


# action 列舉值（用常數避免打錯字；存進 DB 仍是字串）。
# 涵蓋「有成交」與「沒成交但有決策」兩類時點。
ACTION_BOUGHT = "bought"                              # 進場買進
ACTION_SOLD = "sold"                                  # 出場賣出（風控或策略）
ACTION_HOLD = "hold"                                  # 續抱 / 空手觀望（沒動作）
ACTION_SKIPPED_MARKET_CLOSED = "skipped_market_closed"      # 休市跳過
ACTION_SKIPPED_NO_BUYING_POWER = "skipped_no_buying_power"  # 購買力不足跳過（step-05）
ACTION_SKIPPED_CIRCUIT_BREAKER = "skipped_circuit_breaker"  # 組合回撤熔斷跳過（step-09）
ACTION_DEMOTED = "demoted"                            # tracking error 自動降級停 Bot（維運安全軌 H3）
ACTION_BOT_CULLED = "bot_culled"                      # 審查員汰弱停 Bot（Phase 13，績效不及格軟汰弱）


# exit_kind 列舉值（只在「賣出」時填，把 ACTION_SOLD 細分成可統計的出場類型）。
# action 仍是粗粒度的 sold（不破壞既有查詢/測試）；exit_kind 補上「為什麼賣」的機器可讀分類，
# 讓週報/月報能算「止損 vs 停利 vs 策略反轉各佔多少、各自的平均盈虧」。
EXIT_KIND_STOP_LOSS = "stop_loss"            # 固定止損觸發（跌破進場價×(1−門檻)）
EXIT_KIND_TAKE_PROFIT = "take_profit"        # 固定止盈觸發（漲到進場價×(1+門檻)）
EXIT_KIND_TRAILING = "trailing"              # 追蹤止損觸發（從持倉最高價回落門檻）
EXIT_KIND_SIGNAL_REVERSAL = "signal_reversal"  # 策略訊號反轉出場（非風控，純策略翻空）
EXIT_KIND_BROKER_SETTLED = "broker_settled"  # 券商端保護單成交、本機回填（出場原因以託管單為準）


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 是哪一個 Bot 的決策（對應 bots.id）
    bot_id = Column(Integer, index=True)

    # 股票代號
    symbol = Column(String, nullable=False)

    # 策略 / 風控當下的訊號："buy" / "sell" / "hold"
    signal = Column(String, nullable=False)

    # 決策原因（策略訊號說明 / 風控觸發原因 / 跳過原因），例如「黃金交叉」「觸發止損」「休市」
    reason = Column(String)

    # 決策當下的參考價（最新成交價；查不到時為 None）
    price = Column(Float, nullable=True)

    # 決策當下那根 K 線的成交量（「量」；查不到/風控出場無 df 時為 None）。
    # 跟價格一起記，事後才看得出「在放量還是縮量時進出場」（讀教訓的關鍵脈絡）。
    volume = Column(Float, nullable=True)

    # 實際下單股數（買進/賣出才有；觀望/續抱/休市/跳過等沒下單的動作為 None）。
    # 跟 TradeLog.qty 同義，但 DecisionLog 連「沒成交但有決策」的時點都收，這裡冗存方便單表回顧。
    qty = Column(Float, nullable=True)

    # 決策當下「該策略看的指標」快照（如 {"rsi":28.1,"ma_short":231.2,"ma_long":228.4}）。
    # 來源：services.indicator_overlays.compute_overlays 取各序列最後一根值（與圖表同公式）。
    # 用 JSON 存（不同策略指標欄位不同）；風控出場/抓不到資料時為 None。
    indicators = Column(JSON, nullable=True)

    # 實際採取的動作（見上方 ACTION_* 常數）
    action = Column(String, nullable=False)

    # ===== 結構化交易日誌擴充（讓週報/月報能回溯「買入假設→賣出失效」）=====
    # 全部 nullable：既有寫入點不傳也不壞，只有「有意義」的時點才填（多半是買進/賣出）。

    # 觸發決策的策略代號（冗存 Bot.strategy，免事後 join；自適應模式記「這輪實際挑中的」）。
    strategy = Column(String, nullable=True)

    # 交易總額 = price × qty（買進/賣出才有；觀望/跳過為 None）。
    total_amount = Column(Float, nullable=True)

    # 預期獲利點 / 預計停損點（決策當下算出的價位，非比例）：
    #   買進：target=進場價×(1+take_profit_pct)、stop=進場價×(1−stop_loss_pct)，未設門檻則 None。
    #   風控出場：填觸發的那條門檻價（止盈填 target、止損填 stop），方便和實際成交價對照。
    target_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)

    # 決策當下的市場快照（JSON）：{"ma5","ma20","ma60","price_vs_ma20_pct","vol_ratio","vol_state",...}。
    # 來源：services.decision_context.compute_market_snapshot(df)，與圖表/指標同一套 pandas 公式。
    # 風控出場/休市等無 df 的時點為 None。回答「進出場時站在均線上方還是下方、放量還是縮量」。
    market_snapshot = Column(JSON, nullable=True)

    # 交易後庫存狀態（JSON，best-effort）：{"shares":交易後持股, "buying_power":剩餘購買力}。
    # 查不到帳戶（離線/無金鑰）時為 None；不阻斷交易主流程。
    position_after = Column(JSON, nullable=True)

    # 賣出時的出場類型（見上方 EXIT_KIND_* 常數；買進/觀望/跳過為 None）。
    exit_kind = Column(String, nullable=True)

    # 賣出時回填「哪個買入假設失效」（一句結構化說明，給人 + LLM 檢討看）：
    # 撈該 Bot 最近一筆 bought 的本表紀錄，把當初的 target/stop/進場價 跟這次出場價/原因對照，
    # 例如「跌破預設停損 $228.0（進場 $240.0，−5.0%）；持有 3 天」。無對應買入紀錄時為 None。
    thesis_breach = Column(String, nullable=True)

    # 決策時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<DecisionLog {self.id} bot={self.bot_id} {self.action} {self.signal} {self.symbol}>"
