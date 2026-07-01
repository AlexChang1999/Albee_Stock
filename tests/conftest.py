"""
pytest 全域設定
================
測試環境一律關閉「開機補跑」：

很多測試用 TestClient(app) 起 FastAPI——lifespan 會掛 schedule_catchup_on_boot，
補跑是「立即執行的一次性背景 job」，會在排程器執行緒**真的**跑
discovery / 領導股回測 / 心跳通知（打網路、發通知、寫 dev DB、
還會跟其他測試的 monkeypatch 打架——曾讓 test_bot_manager 撈到別執行緒的呼叫）。

test_catchup.py 自己會在測試內把 CATCHUP_ON_BOOT 打開來測補跑邏輯（用 stub，不打網）。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 測試一律走本機 SQLite，永不連 Neon（根治 flaky）──────────────────────
# 全域 engine / SessionLocal 在 import backend.database 當下就用 settings.DATABASE_URL
# 建好定型。lifespan 的 init_db/resume/排程，與 validate-batch 背景任務自建的
# SessionLocal，都直接吃這顆全域 engine、不經過 get_db 覆寫——只要它指向 Neon，測試
# 就會連雲端（慢/idle 斷線 → flaky）。在最早期把 DATABASE_URL 指到暫存 SQLite，
# 全域 engine 即為本機檔案，整個測試程序與 Neon 徹底脫鉤。各測試仍各自用 tmp_path
# SQLite 覆寫 get_db 做逐測試隔離；本檔只負責「全域安全網」這一層。
# config.py 的 load_dotenv(override=False) 不會覆蓋既有環境變數，故此值贏過 .env。
_TEST_DB = Path(tempfile.gettempdir()) / "albee_stock_test.db"
_TEST_DB.unlink(missing_ok=True)  # 每次 session 全新，不累積前次殘留
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from backend.config import settings


@pytest.fixture(autouse=True)
def _disable_boot_side_effects(monkeypatch):
    """每個測試預設：不開機補跑、不掛每日領導股回測（避免背景真跑回測/通知）。"""
    monkeypatch.setattr(settings, "CATCHUP_ON_BOOT", False)
    monkeypatch.setattr(settings, "LEADER_BACKTEST_ENABLED", False)
