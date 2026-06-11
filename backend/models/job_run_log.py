"""
每日 job 跑次紀錄資料模型（開機補跑用）
========================================
記「哪個每日排程 job、哪一天、成功跑過了」。給兩個地方共用：

1. **開機補跑**（services/catchup.py）：後端啟動時查「今天該跑的 job 跑過沒」，
   沒跑且時刻已過就補跑——家用電腦不是 24/7，早上 7/8 點沒開機，
   discovery/auto_validate 等每日管線會整天跳過，這張表讓它們補得回來。
2. **同日防重複**：cron 正常觸發與開機補跑共用同一張表判斷，
   同一個 job 同一天只會實際執行一次。

設計原則：**只記成功的跑次**。失敗不落紀錄 → 下次開機或當天稍後的 cron
自然重試，不需要額外的重試機制。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from backend.database import Base


class JobRunLog(Base):
    __tablename__ = "job_run_log"

    id = Column(Integer, primary_key=True, index=True)

    # job 名稱，沿用排程器的 job id（如 discovery_bridge / auto_validate / heartbeat_daily）
    job_name = Column(String, index=True, nullable=False)

    # 跑的日期（本機時區，"YYYY-MM-DD"）——「今天跑過沒」就是比對這欄
    run_date = Column(String, index=True, nullable=False)

    # 實際完成時刻
    ran_at = Column(DateTime, default=datetime.now)

    # 簡短結果摘要（如 discovery 回傳的統計 dict 轉字串），可空
    detail = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<JobRunLog {self.job_name} @ {self.run_date}>"
