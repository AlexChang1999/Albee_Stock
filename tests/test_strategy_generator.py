"""
策略生成器測試（Phase 8 step-02）
===================================
驗證：
1. _parse_param_list 從模型回覆穩健抓出參數陣列（含夾雜文字、亂回的情況）。
2. propose_params：monkeypatch LLM 回傳 → 解析出合法參數清單、裁到 n。
3. 非法策略鍵被擋（ValueError），且不需碰 LLM。

不連網、不碰 DB（DB 寫入是 router 的事，另由 API 測試覆蓋）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_strategy_generator.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services import llm, strategy_generator
from backend.services.strategy_generator import _parse_param_list, propose_params


def test_parse_param_list():
    """容忍夾雜文字、只取 JSON 陣列；亂回 → 空清單。"""
    raw = '好的，建議如下：[{"period": 14}, {"period": 21}] 希望有幫助'
    assert _parse_param_list(raw) == [{"period": 14}, {"period": 21}]
    assert _parse_param_list("沒有 JSON") == []
    assert _parse_param_list('{"period": 14}') == []  # 物件非陣列 → 空
    # 陣列裡非 dict 的元素被丟棄
    assert _parse_param_list('[{"a":1}, "x", 3]') == [{"a": 1}]


def test_propose_params_parses_and_caps(monkeypatch):
    """monkeypatch LLM 回傳 → 解析出參數，且裁到 n。"""
    monkeypatch.setattr(
        llm, "complete",
        lambda client, messages, max_tokens=512: '[{"period": 7}, {"period": 14}, {"period": 21}]',
    )
    out = propose_params(client=object(), strategy_key="rsi", scenario="震盪盤均值回歸", n=2)
    assert out == [{"period": 7}, {"period": 14}]


def test_propose_params_illegal_key():
    """非法策略鍵 → ValueError（不需碰 LLM）。"""
    try:
        propose_params(client=object(), strategy_key="不存在的策略", scenario="x", n=3)
        assert False, "非法策略鍵應 raise ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_parse_param_list()
    test_propose_params_illegal_key()
    print("（propose_params 的 LLM 測試需 pytest 的 monkeypatch，請用 pytest 執行）")
    print("\n🎉 策略生成器純函式測試通過！")
