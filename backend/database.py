"""
資料庫連線設定
==============
用 SQLAlchemy 管理 SQLite 資料庫。

幾個名詞解釋（新手友善）：
- engine（引擎）：實際跟資料庫溝通的核心物件。
- Session（連線階段）：每次要讀寫資料時，開一個 session 來操作。
- Base：所有「資料表模型」的共同父類別（在 models/ 裡會用到）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

# 建立資料庫引擎。
# connect_args={"check_same_thread": False} 是 SQLite 在多執行緒環境
# （例如 FastAPI + 排程器）需要的設定，否則會報錯。
# ⚠️ 這個參數**只有 SQLite 認得**：換成 PostgreSQL 等其他資料庫時若硬塞會報
# 「invalid connection option」。所以依 DATABASE_URL 的方言判斷，只在 SQLite 才加，
# 兌現 CLAUDE.md「換 PostgreSQL 只改 .env、程式不用改」的承諾。
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# 雲端 PostgreSQL（Neon）會把「閒置太久」的連線從伺服器端直接斷掉，連線池裡那條
# 已死的 socket 下次拿來用就炸 `SSL connection has been closed unexpectedly`
# （collector/排程的背景工作最容易踩到，因為兩次掃描間隔很長）。
# 兩道防護（只對非 SQLite 的雲端 DB 加；SQLite 是本機檔案不需要）：
#   - pool_pre_ping=True：每次從池子借連線前先送一個輕量 ping，發現連線死掉就丟掉重建。
#   - pool_recycle=300：超過 300 秒的連線主動回收，不等它被伺服器端悄悄掐死。
_pool_kwargs = {} if _is_sqlite else {"pool_pre_ping": True, "pool_recycle": 300}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=False,  # 設 True 會印出每一句 SQL，除錯時很有用
    **_pool_kwargs,
)

# SessionLocal 是「製造 session 的工廠」，要用時呼叫 SessionLocal() 拿一個。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 所有資料表模型都要繼承這個 Base
Base = declarative_base()


def get_db():
    """
    提供一個資料庫 session，用完自動關閉。
    FastAPI 的路由會用 Depends(get_db) 取得它。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建立所有資料表（如果還沒建立的話）。程式啟動時呼叫一次。"""
    # 匯入 models 讓 SQLAlchemy 知道有哪些資料表要建立
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("✅ 資料庫初始化完成")
