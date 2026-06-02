"""
LLM 思考助手 API 測試 ── Phase 5
================================================
只測「不需真的呼叫 LLM」的部分：
- 沒設定 LLM（LLM_BASE_URL 空）→ /chat 與 /chat/postmortem 都回 400（不崩潰）。
- messages 空 → 400（不會白白打 LLM）。
- 連不上 LLM 服務（指到沒人聽的埠）→ 優雅回 400 + Ollama 啟動提示，而非 500/掛掉。
真正的對話/檢討需本機啟動 Ollama（或接其他供應商）後自行驗證，不納入自動測試。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_chat.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings

client = TestClient(app)


def test_chat_no_llm_configured_returns_400(monkeypatch):
    """沒設定 LLM（base_url 空）時 /chat 回 400 並提示去設定，而非崩潰。"""
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "嗨"}]})
    assert r.status_code == 400, r.text
    assert "LLM" in r.json()["detail"]
    print("✅ /chat 未設定 LLM 回 400 測試通過")


def test_postmortem_no_llm_returns_400(monkeypatch):
    """沒設定 LLM 時 /chat/postmortem 也回 400。"""
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    r = client.post("/chat/postmortem", json={"run_id": 1})
    assert r.status_code == 400, r.text
    assert "LLM" in r.json()["detail"]
    print("✅ /chat/postmortem 未設定 LLM 回 400 測試通過")


def test_chat_empty_messages_returns_400():
    """messages 空 → 400（用預設 Ollama base_url，在連線前就擋掉，不需真的有 Ollama）。"""
    r = client.post("/chat", json={"messages": []})
    assert r.status_code == 400, r.text
    assert "messages" in r.json()["detail"]
    print("✅ /chat 空 messages 回 400 測試通過")


def test_chat_connection_error_is_graceful(monkeypatch):
    """連不上 LLM（指到沒人聽的埠）→ 應優雅回 400 並給 Ollama 提示，而非 500。"""
    # 127.0.0.1:9（discard 埠）通常無人監聽，連線會被立刻拒絕
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3.1")
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "嗨"}]})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "Ollama" in detail or "LLM" in detail
    print("✅ /chat 連不上服務優雅回 400 測試通過")


if __name__ == "__main__":
    # 手動跑：直接清空 base_url 驗證 400
    settings.LLM_BASE_URL = ""
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "嗨"}]})
    assert r.status_code == 400, r.text
    print("✅ 手動驗證：/chat 未設定 LLM 回 400")
    print("\n🎉 chat 測試通過！")
