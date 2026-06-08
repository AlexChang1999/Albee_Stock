"""
策略生成器（LLM 提案）── Phase 8 step-02
==========================================
依知識庫的「理論 / 場景」描述，請 LLM **草擬**幾組候選參數，產出進「候選區」
（StrategyKnowledge.status=candidate）。**生成只負責提出假設，不負責判斷好壞**：
草擬不等於上線，未過驗證管線（step-04）不准進策展庫。

職責分離（生成 ≠ 驗證 ≠ 部署）：
- 本模組只「草擬參數 + 回傳」，不跑回測、不寫 DB、不部署（DB 寫入在 router）。
- 只限定既有 STRATEGY_REGISTRY 的策略鍵；**不**自動生成新的策略 .py
  （自動寫碼＝失控源頭，新策略邏輯一律走 strategy-builder skill 由人驅動）。

沿用既有 LLM 低階工具（backend.services.llm），外送安全閥（LLM_ALLOW_CLOUD）只有一份、
不自寫 LLM 呼叫；連不上 → 由 router 優雅回 400，不阻斷其他功能。
"""

import json

from backend.services import llm
from backend.strategies import STRATEGY_REGISTRY

_MAX_TOKENS = 512


def _parse_param_list(raw: str) -> list[dict]:
    """從模型回覆裡穩健抓出 JSON 物件陣列（每個元素是一組參數 dict）。抓不到回空清單。

    與 chat._parse_filename_list 同精神：容忍模型在 JSON 前後夾雜文字，
    只取第一個 '[' 到最後一個 ']' 之間嘗試解析。
    """
    if not raw:
        return []
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    # 只保留 dict 元素（一組參數），其餘丟棄
    return [x for x in data if isinstance(x, dict)]


def propose_params(client, strategy_key: str, scenario: str, n: int = 3) -> list[dict]:
    """
    請 LLM 依「場景描述」為某個既有策略建議 n 組參數（純提案，不寫 DB、不回測）。

    :param client: 已建好的 OpenAI 相容 client（由 router 用 llm.get_client 建立並做外送閘檢查）
    :param strategy_key: 策略代號，**必須**是 STRATEGY_REGISTRY 既有的鍵
    :param scenario: 場景 / 理論描述（例如「高波動震盪盤，想抓均值回歸」）
    :param n: 想要幾組（上限裁切）
    :return: 參數 dict 清單（可能少於 n；模型亂回時可能為空）
    :raises ValueError: 非法策略鍵（不在註冊表）
    """
    if strategy_key not in STRATEGY_REGISTRY:
        raise ValueError(
            f"未知的策略鍵：{strategy_key}，只能用既有策略：{list(STRATEGY_REGISTRY.keys())}"
        )

    sys_text = (
        "你是量化策略參數建議器。只回 JSON 物件陣列，不要任何多餘文字或說明。"
        "每個物件是一組該策略的參數（鍵為參數名、值為數字）。"
    )
    user_text = (
        f"策略代號：{strategy_key}\n"
        f"適用場景 / 理論：{scenario}\n\n"
        f"請建議 {n} 組適合此場景的參數，只回 JSON 陣列，"
        '例如 [{"period": 14}, {"period": 21}]。沒有把握就回 []。'
    )
    raw = llm.complete(
        client,
        [{"role": "system", "content": sys_text},
         {"role": "user", "content": user_text}],
        max_tokens=_MAX_TOKENS,
    )
    return _parse_param_list(raw)[: max(0, n)]
