"""
策略清單單一來源測試（Phase 6 step-10）
=========================================
1. GET /strategies 端點往返：回 [{value, label}]，value 集合 == 後端註冊表鍵集合。
2. 前後端一致：斷言「後端註冊鍵集合 == 前端 constants.js 的 value 集合」，
   消除「新增策略卻忘了同步前端清單」的漂移（消滅多處手動同步）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_strategies_registry.py -q
"""

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.strategies import STRATEGY_REGISTRY


def test_strategies_endpoint():
    """GET /strategies 回 [{value,label}]，value 集合等於註冊表鍵集合。"""
    with TestClient(app) as client:
        resp = client.get("/strategies")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list) and body, body
        for item in body:
            assert "value" in item and "label" in item and item["label"], item
        values = {item["value"] for item in body}
        assert values == set(STRATEGY_REGISTRY.keys()), (values, set(STRATEGY_REGISTRY))
    print("✅ GET /strategies 往返測試通過")


def test_frontend_constants_match_backend_registry():
    """前端 constants.js 的策略 value 集合，必須等於後端註冊表鍵集合。"""
    constants = (ROOT / "frontend" / "src" / "constants.js").read_text(encoding="utf-8")
    # 抓 STRATEGIES 陣列裡每個 { value: "xxx", ... } 的 value
    frontend_values = set(re.findall(r'value:\s*"([^"]+)"', constants))
    backend_keys = set(STRATEGY_REGISTRY.keys())
    assert frontend_values == backend_keys, (
        f"前後端策略清單不同步！僅前端有：{frontend_values - backend_keys}；"
        f"僅後端有：{backend_keys - frontend_values}"
    )
    print("✅ 前後端策略清單一致測試通過")


if __name__ == "__main__":
    test_strategies_endpoint()
    test_frontend_constants_match_backend_registry()
    print("\n🎉 策略清單單一來源測試全通過！")
