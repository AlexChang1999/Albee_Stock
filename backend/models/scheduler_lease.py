"""
排程器選主「租約」資料模型
==========================
取代舊的 PostgreSQL advisory lock 選主機制。

為什麼要換掉 advisory lock？
- advisory lock 綁在「持有它的那條連線」上。Neon（serverless PostgreSQL）會把
  閒置太久的連線從伺服器端掐斷 → 鎖被悄悄釋放，但持有者渾然不覺，
  繼續自以為是 leader → 另一個實例搶到鎖 → **雙 leader 同時下單**（真金風險）。
- 租約（lease）制不依賴長連線：leader 必須「定期續約」才能保住身分，
  續不了約（斷線、被搶）就立刻自貶為 follower、停止下單。

表設計：**永遠只有 id=1 這一列**（單列表，比照 portfolio_state 的做法）。
- holder_id：目前 leader 的識別碼（每個 process 開機時隨機產生的 uuid）
- hostname：持有者機器名（純除錯用，看 log 就知道現在誰是 leader）
- acquired_at / expires_at：取得時間 / 到期時間（都用「資料庫時鐘」的 UTC，
  避免多台機器系統時鐘不同步造成誤判）

搶鎖規則（原子 UPDATE，詳見 services/scheduler_lock.py）：
- 租約過期（expires_at < now）或本來就是自己的 → 可以拿走
- 還在有效期且是別人的 → 搶不到，當 follower
"""

from sqlalchemy import Column, Integer, String, DateTime

from backend.database import Base


class SchedulerLease(Base):
    __tablename__ = "scheduler_lease"

    # 固定單列：永遠用 id=1 這一筆
    id = Column(Integer, primary_key=True, index=True)

    # 目前持有者（process 級 uuid）；NULL = 沒人持有
    holder_id = Column(String(64), nullable=True)

    # 持有者機器名（除錯用）
    hostname = Column(String(255), nullable=True)

    # 取得租約的時間（DB 時鐘 UTC）
    acquired_at = Column(DateTime, nullable=True)

    # 租約到期時間（DB 時鐘 UTC）；過期即可被任何實例接手
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SchedulerLease holder={self.holder_id} host={self.hostname} expires={self.expires_at}>"
