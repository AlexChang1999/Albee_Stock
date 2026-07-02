"""
排程器選主鎖（租約制，防多實例重複下單 / 重複推播）
=====================================================

問題情境
--------
搬上雲後，可能同時有「地端後端」+「雲端 VM 後端」兩個 process 都連同一個 Neon
PostgreSQL。兩邊的 lifespan 都會掛「對外動作」的排程 job（Bot 下單、推播、心跳…）
→ 同一件事被做兩次（重複下單、重複推播、互蓋止損）。

舊解法的死穴（為什麼重寫）
--------------------------
舊版用 PostgreSQL session advisory lock：鎖綁在「持有它的那條連線」上，
且**只在開機時檢查一次**。Neon 會掐斷閒置連線 → 鎖被悄悄釋放，但持有者
渾然不覺、繼續自以為是 leader → 另一實例搶到鎖 → **雙 leader 同時下單**。

新解法：租約（lease）+ 定期續約 + 自動升降級
--------------------------------------------
- 單列資料表 `scheduler_lease`（id=1），不依賴任何長連線。
- 搶鎖 = 一句**原子 UPDATE**：「租約是我的、或已過期 → 換成我、續期 TTL」。
  影響 1 列 = 搶到；0 列 = 別人還持有有效租約。
- leader 每 RENEW 秒續約一次：
  - 續約 UPDATE 影響 0 列 → 租約被別人拿走了 → **立即降級**（停排程、停下單）。
  - DB 例外連續 2 次 → 無法證明自己還是 leader → **保守降級**。
- follower 每輪嘗試搶租約，搶到 → **自動升級**（掛回排程）。
  → VM 重啟後不用人工介入，租約過期（TTL 90 秒）內自動接手。
- 時間一律用「資料庫時鐘」的 UTC（`_db_now`），避免多台機器時鐘不同步誤判。

最後防線
--------
alpaca_client 的所有 submit_* 下單函式開頭都會呼叫本模組的 `assert_leader()`：
即使降級訊號沒趕上正在跑的執行緒，訂單送出前仍會被擋下（第三閘，與
實盤雙閘並列）。

SQLite（單機、`.env` 沒填 DATABASE_URL）時無多實例競爭：`is_leader()` 恆 True，
行為與沒這功能一樣。但底層租約函式（_try_acquire/_renew）在 SQLite 上照樣能跑，
pytest 直接用 SQLite 模擬兩個 holder 互搶。
"""

import socket
import threading
import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, text, update, insert

from backend.config import settings
from backend.database import engine
from backend.models.scheduler_lease import SchedulerLease

# ---- 租約參數 ----
LEASE_TTL_SEC = 90        # 租約有效期：leader 斷線後最慢 90 秒被接手
LEASE_RENEW_SEC = 30      # leader 續約間隔（TTL 的 1/3，容忍偶發一次失敗）
_MAX_RENEW_FAILURES = 2   # DB 例外連續 N 次 → 保守降級（無法證明自己還是 leader）

# ---- 本 process 的身分 ----
_HOLDER_ID = uuid.uuid4().hex          # 每次開機隨機產生，識別「這個 process」
_HOSTNAME = socket.gethostname()

# ---- 狀態旗標（記憶體快取，下單熱路徑零 DB 查詢）----
_leader_flag = False
_renew_failures = 0
_flag_lock = threading.Lock()  # 升降級切換由 daemon 執行緒觸發，加鎖保險


def _is_postgres() -> bool:
    """目前是不是接 PostgreSQL（Neon）。SQLite 單機無多實例競爭。"""
    return settings.DATABASE_URL.startswith("postgresql")


def _db_now(conn) -> datetime:
    """
    取「資料庫時鐘」的 UTC 時間（naive datetime）。

    為什麼不用 Python 的 datetime.now()：多台機器（地端 + VM）系統時鐘可能不同步，
    租約的「過期與否」必須用同一顆時鐘判斷才公平——就用 DB 自己的。

    注意：這裡看「連線的實際方言」而非 _is_postgres()（settings 判斷）——
    測試會 monkeypatch _is_postgres 模擬多實例情境，但底層 DB 仍是 SQLite。
    """
    if conn.dialect.name == "postgresql":
        return conn.execute(text("SELECT now() AT TIME ZONE 'utc'")).scalar()
    # SQLite 的 CURRENT_TIMESTAMP 本來就是 UTC（回傳字串或 datetime，依驅動而定）
    raw = conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar()
    if isinstance(raw, datetime):
        return raw
    return datetime.strptime(str(raw).split(".")[0], "%Y-%m-%d %H:%M:%S")


def _ensure_row(conn) -> None:
    """確保 id=1 那一列存在（第一次跑或全新 DB）。撞到別人同時插入就當作已存在。"""
    exists = conn.execute(
        text("SELECT 1 FROM scheduler_lease WHERE id = 1")
    ).scalar()
    if not exists:
        try:
            conn.execute(insert(SchedulerLease).values(id=1))
        except Exception:
            pass  # 兩個實例同時初始化：另一邊已插入，忽略即可


def _try_acquire(holder_id: str = None) -> bool:
    """
    原子搶租約。回傳是否搶到。

    UPDATE 條件：「租約是我的（續約）or 沒人持有 or 已過期」→ 換成我 + 續期 TTL。
    影響 1 列 = 搶到；0 列 = 別人還持有有效租約。
    這一句 UPDATE 在 DB 端是原子的：兩個實例同時搶，只有一個會改到列。
    """
    holder = holder_id or _HOLDER_ID
    try:
        with engine.begin() as conn:
            _ensure_row(conn)
            now = _db_now(conn)
            stmt = (
                update(SchedulerLease)
                .where(
                    SchedulerLease.id == 1,
                    or_(
                        SchedulerLease.holder_id == holder,
                        SchedulerLease.holder_id.is_(None),
                        SchedulerLease.expires_at.is_(None),
                        SchedulerLease.expires_at < now,
                    ),
                )
                .values(
                    holder_id=holder,
                    hostname=_HOSTNAME,
                    acquired_at=now,
                    expires_at=now + timedelta(seconds=LEASE_TTL_SEC),
                )
            )
            return conn.execute(stmt).rowcount == 1
    except Exception as e:
        # 搶不到就搶不到，保守當 follower（避免兩邊都做）
        print(f"⚠️  排程器選主：搶租約時發生例外，暫當 follower（{e}）")
        return False


def _renew(holder_id: str = None) -> bool:
    """
    續約（只有還持有租約才會成功）。回傳是否續成。

    影響 0 列 = 租約已被別人拿走（我斷線太久、過期被接手）→ 呼叫端必須立即降級。
    DB 例外 → 丟出去，由 daemon 計數（連續失敗才降級，容忍偶發抖動）。
    """
    holder = holder_id or _HOLDER_ID
    with engine.begin() as conn:
        now = _db_now(conn)
        stmt = (
            update(SchedulerLease)
            .where(SchedulerLease.id == 1, SchedulerLease.holder_id == holder)
            .values(expires_at=now + timedelta(seconds=LEASE_TTL_SEC))
        )
        return conn.execute(stmt).rowcount == 1


def _release(holder_id: str = None) -> None:
    """讓出租約（正常關機用）：清空持有者，讓其他實例「立刻」接手，不用等 TTL。"""
    holder = holder_id or _HOLDER_ID
    try:
        with engine.begin() as conn:
            conn.execute(
                update(SchedulerLease)
                .where(SchedulerLease.id == 1, SchedulerLease.holder_id == holder)
                .values(holder_id=None, hostname=None, acquired_at=None, expires_at=None)
            )
    except Exception:
        pass  # 關機時 DB 連不上就算了，租約 TTL 到期自然被接手


# ---------- 對外介面 ----------

def is_leader() -> bool:
    """
    我現在是不是 leader（記憶體旗標，不打 DB——下單熱路徑用）。

    SQLite 單機恆 True（無競爭）。PostgreSQL 下只有「開機搶到 or 續約成功中」才 True。
    """
    if not _is_postgres():
        return True
    return _leader_flag


def assert_leader() -> None:
    """
    下單最後防線（第三閘，與實盤雙閘並列）。

    非 leader 呼叫任何下單函式 → 直接拒絕。即使降級訊號沒趕上正在跑的
    Bot 執行緒，訂單送出前仍會在這裡被擋下，杜絕雙 leader 重複下單。
    """
    if not is_leader():
        raise RuntimeError(
            "拒絕下單：本實例不是排程 leader（租約已失效或被其他實例持有）。"
            "為避免雙 leader 重複下單，非 leader 一律不可送出任何訂單。"
        )


def acquire_scheduler_lock() -> bool:
    """
    開機時嘗試成為排程 leader（介面名沿用舊版，main.py 呼叫處不用改語意）。

    :return: True = 我是 leader（該掛對外排程）；False = 已有別的實例當 leader。
    """
    global _leader_flag
    if not _is_postgres():
        _leader_flag = True
        return True
    got = _try_acquire()
    with _flag_lock:
        _leader_flag = got
    return got


def release_scheduler_lock() -> None:
    """正常關機：讓出租約（其他實例可立刻接手，不用等 TTL 過期）。"""
    global _leader_flag
    with _flag_lock:
        _leader_flag = False
    if _is_postgres():
        _release()


def start_lease_daemon(scheduler, on_promote, on_demote) -> None:
    """
    掛上「租約守護」定時 job（leader 續約 / follower 搶位，每 LEASE_RENEW_SEC 秒一輪）。

    :param scheduler: APScheduler 實例（借 bot_manager 那顆，不另開執行緒）
    :param on_promote: follower 搶到租約時呼叫（掛回所有對外排程）
    :param on_demote: leader 失去租約時呼叫（卸下所有對外排程）

    無論開機時是 leader 還是 follower 都要掛這個 job：
    - leader 靠它定期驗證「租約還是不是我的」（修復舊版只查一次的死穴）
    - follower 靠它在前任斷線後自動接手（VM 重啟零人工介入）

    SQLite 單機不掛（無競爭，恆為 leader）。
    """
    if not _is_postgres():
        return

    def _tick() -> None:
        global _leader_flag, _renew_failures
        if _leader_flag:
            # --- leader：續約 + 驗鎖 ---
            try:
                ok = _renew()
                _renew_failures = 0
                if not ok:
                    # 影響 0 列 = 租約已被別人拿走 → 立即降級，不可再送任何訂單
                    _demote(on_demote, reason="租約已被其他實例接手")
            except Exception as e:
                _renew_failures += 1
                print(f"⚠️  排約續約失敗（{_renew_failures}/{_MAX_RENEW_FAILURES}）：{e}")
                if _renew_failures >= _MAX_RENEW_FAILURES:
                    # 連續失敗 → 無法證明自己還是 leader → 保守降級（停新單、不平倉）
                    _demote(on_demote, reason=f"連續 {_renew_failures} 次無法續約")
        else:
            # --- follower：嘗試接手 ---
            if _try_acquire():
                with _flag_lock:
                    _leader_flag = True
                _renew_failures = 0
                print(f"🟢 本實例（{_HOSTNAME}）已升級為排程 leader，掛回對外排程")
                _safe_notify(f"🟢 排程 leader 已切換到 {_HOSTNAME}（自動接手）")
                try:
                    on_promote()
                except Exception as e:
                    print(f"⚠️  升級掛排程時發生例外：{e}")

    scheduler.add_job(
        _tick,
        "interval",
        seconds=LEASE_RENEW_SEC,
        id="scheduler_lease_daemon",
        replace_existing=True,
    )


def _demote(on_demote, reason: str) -> None:
    """降級為 follower：先立旗（擋住後續下單），再卸排程、發告警。"""
    global _leader_flag, _renew_failures
    with _flag_lock:
        _leader_flag = False  # 最先做：assert_leader 立刻開始擋單
    _renew_failures = 0
    print(f"🔴 本實例（{_HOSTNAME}）已降級為 follower：{reason}。停止交易與對外排程。")
    try:
        on_demote()
    except Exception as e:
        print(f"⚠️  降級卸排程時發生例外：{e}")
    _safe_notify(
        f"🔴 排程 leader 降級：{_HOSTNAME}（{reason}）。"
        f"本實例已停止下單與推播；持倉由券商端 GTC 保護單守護，不自動平倉。"
    )


def _safe_notify(message: str) -> None:
    """發通知（失敗不影響升降級流程本身）。延遲 import 避免循環依賴。"""
    try:
        from backend.services.notifier import notify
        notify(message)
    except Exception:
        pass
