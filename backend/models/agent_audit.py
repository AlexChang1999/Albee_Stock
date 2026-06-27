"""
Agent Gateway 審計軌跡資料模型（採納自 QuantDinger 的 append-only audit log）
=========================================================================
外部 AI agent（Claude / Cursor 等）每次打 /api/agent/v1/* 都在這裡留一筆紀錄。

為什麼要有：agent 能自動驅動回測、查資料、甚至下 paper 單，自動化系統的每個外部動作
都該事後查得到（「昨天是哪支 agent 用什麼 token 下了這張單？」）。這是 append-only
（只新增、不更新/刪除）的軌跡，比照 DecisionLog 的精神。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON

from backend.database import Base


class AgentAudit(Base):
    __tablename__ = "agent_audits"

    id = Column(Integer, primary_key=True, index=True)

    # 呼叫的端點路徑，例如 "/api/agent/v1/backtest"
    endpoint = Column(String, nullable=False, index=True)

    # token 標籤：方便辨識是哪把 token（目前單 token，固定記 "default"；未來多 token 用得上）。
    # ★ 絕不記 token 本身（避免明文外洩），只記人看得懂的標籤。
    token_label = Column(String, nullable=True)

    # 呼叫帶的參數快照（JSON）：例如 {"strategy":"rsi","symbol":"AAPL","days":365}。
    # 下單端點會記方向/股數/標的，方便事後對帳。
    params = Column(JSON, nullable=True)

    # 結果狀態："ok" / "error" / "rejected"（被閘擋下，如想下真錢單但閘沒開）。
    status = Column(String, nullable=False)

    # 補充說明（錯誤訊息 / 拒絕原因 / 簡短結果摘要）。
    detail = Column(String, nullable=True)

    # 呼叫時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<AgentAudit {self.id} {self.endpoint} {self.status}>"
