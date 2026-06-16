"""
排程器選主鎖（防多實例重複推播 / 重複下單）
==============================================

問題情境
--------
搬上雲後，可能同時有「地端後端」+「雲端 VM 後端」兩個 process 都連同一個 Neon
PostgreSQL。兩邊的 `lifespan` 都會掛上會「對外動作」的排程 job（政治員通知、
collector 通知、心跳、Bot 下單…）→ 同一件事被做兩次（重複推播、重複下單、互蓋止損）。

解法：選主（leader election）
----------------------------
用 PostgreSQL 的 **advisory lock**（諮詢鎖）做最簡單的選主：
- 開機時搶一把固定 key 的 session 級 advisory lock。
- **搶到的那個 process = leader**，才掛對外推播 / 下單的排程。
- 沒搶到的 = follower，只當唯讀 API（前端照常連得到），不掛對外 job。
- advisory lock 綁在「持有它的那條連線」上：連線一斷（process 掛掉 / 重啟），
  鎖自動釋放，另一個 process 下次開機就能接手。**不會卡死**。

純 SQLite（`.env` 沒填 `DATABASE_URL`）時用不到——單機本來就不會有兩個實例互搶，
直接回報「我是 leader」即可，行為與沒這功能一樣。

新手提醒：advisory lock 是「應用程式自己約定意義」的鎖，PostgreSQL 不會拿它去鎖任何
資料表，純粹當旗標用。key 只要全系統講好同一個數字即可。
"""

from sqlalchemy import text

from backend.config import settings
from backend.database import engine

# 全系統講好的固定 key（任意 bigint，只要不和其他 advisory lock 撞）。
# 取自 "albee" 的諧音數字，純粹是個獨一無二的常數。
_SCHEDULER_LOCK_KEY = 728_531_001

# 持有鎖的那條連線必須「活著」整個 process 生命週期——一旦被回收關閉，鎖就釋放了。
# 所以用模組級變數把它釘住，別讓它被 GC。
_lock_conn = None


def _is_postgres() -> bool:
    """目前是不是接 PostgreSQL（Neon）。SQLite 沒有 advisory lock。"""
    return settings.DATABASE_URL.startswith("postgresql")


def acquire_scheduler_lock() -> bool:
    """
    嘗試成為排程 leader。

    :return: True = 我是 leader（該掛對外排程）；False = 已有別的實例當 leader（我只當 API）。

    - SQLite：永遠回 True（單機無競爭）。
    - PostgreSQL：搶 advisory lock，搶到回 True、搶不到回 False。
    """
    global _lock_conn

    if not _is_postgres():
        return True

    # 開一條專屬連線並「持有不放」，鎖才會跟著 process 活著。
    conn = engine.connect()
    try:
        # pg_try_advisory_lock：搶得到回 true、被別人佔著回 false（非阻塞，不會卡住開機）。
        got = conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _SCHEDULER_LOCK_KEY}
        ).scalar()
    except Exception as e:
        # 搶鎖失敗（DB 暫時連不上等）→ 保守當「不是 leader」，避免兩邊都搶著做。
        conn.close()
        print(f"⚠️  排程器選主：搶鎖時發生例外，暫不掛對外排程（{e}）")
        return False

    if got:
        _lock_conn = conn  # 釘住連線，維持鎖
        return True

    conn.close()
    return False


def release_scheduler_lock() -> None:
    """釋放鎖（關閉持有連線）。正常關機時呼叫；process 被砍時 DB 端也會自動釋放。"""
    global _lock_conn
    if _lock_conn is not None:
        try:
            _lock_conn.close()  # 連線關閉 → advisory lock 自動釋放
        finally:
            _lock_conn = None
