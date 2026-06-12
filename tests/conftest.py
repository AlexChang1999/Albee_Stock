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

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings


@pytest.fixture(autouse=True)
def _disable_boot_side_effects(monkeypatch):
    """每個測試預設：不開機補跑、不掛每日領導股回測（避免背景真跑回測/通知）。"""
    monkeypatch.setattr(settings, "CATCHUP_ON_BOOT", False)
    monkeypatch.setattr(settings, "LEADER_BACKTEST_ENABLED", False)
