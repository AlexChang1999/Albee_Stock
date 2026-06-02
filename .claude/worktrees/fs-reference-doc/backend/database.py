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
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # 設 True 會印出每一句 SQL，除錯時很有用
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
