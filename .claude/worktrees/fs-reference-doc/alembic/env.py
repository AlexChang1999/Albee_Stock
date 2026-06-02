"""
Alembic 遷移環境設定
====================
這個檔案是 Alembic 每次跑遷移時都會載入的「進入點」。
我們在這裡做三件客製化：

1. 不要用 alembic.ini 裡寫死的 sqlalchemy.url，改成讀專案 config 的 DATABASE_URL
   → 這樣現在跟著 SQLite、未來換 Postgres 都自動跟著走，不用改兩個地方。
2. 把所有 SQLAlchemy model 的 metadata 掛上去，autogenerate 才認得我們的資料表。
3. SQLite 必開 batch 模式（render_as_batch=True），否則未來「改欄位/刪欄位」
   的遷移在 SQLite 會失敗（SQLite 的 ALTER 能力很弱）。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- 客製 1：讓 Alembic 用得到專案的設定與 model ---
from backend.config import settings
from backend.database import Base
import backend.models  # noqa: F401  只為了「import 一下」觸發 model 註冊到 Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 用專案 config 的 DATABASE_URL 覆寫 alembic.ini 的連線字串。
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- 客製 2：掛上所有 model 的 metadata，給 autogenerate 用 ---
target_metadata = Base.metadata

# SQLite 用 batch 模式：把不支援的 ALTER 包成「建新表→搬資料→換名」的批次操作。
_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    """離線模式：只用 URL、不建立實際連線，產出 SQL 字串。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_IS_SQLITE,  # 客製 3：SQLite batch 模式
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """線上模式：建立連線後真的對資料庫跑遷移（一般用這個）。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_IS_SQLITE,  # 客製 3：SQLite batch 模式
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
