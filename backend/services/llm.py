"""
共用 LLM 低階工具（OpenAI 相容介面，預設接本機 Ollama）
========================================================
把「建立 client + 隱私外送閘 + 呼叫 + 友善錯誤」這幾件事集中一處，
讓需要用到本機 LLM 的功能（思考助手、AI 海選的情緒打分…）都共用同一套，
特別是**外送安全閥**只有一份定義，不會這裡開那裡漏。

鐵則（與 chat router 一致）：
- 預設只允許本機（localhost）跑 LLM，資料不離開這台電腦。
- LLM_BASE_URL 指向外部雲端、又沒開 LLM_ALLOW_CLOUD → 一律擋下。
"""

from urllib.parse import urlparse

from backend.config import settings

# 視為「本機」的主機名（資料不離開這台電腦）
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

_TIMEOUT_SEC = 120  # 本機 CPU 生成可能較慢，逾時給寬一點


def is_local_llm() -> bool:
    """LLM_BASE_URL 是否指向本機。解析不出 host 時，保守當作非本機。"""
    host = (urlparse(settings.LLM_BASE_URL).hostname or "").lower()
    return host in _LOCAL_HOSTS


def cloud_blocked() -> bool:
    """指向外部雲端、卻沒開外送閘 → 擋下（隱私安全閥）。"""
    return (not is_local_llm()) and (not settings.LLM_ALLOW_CLOUD)


def get_client():
    """
    建立 OpenAI 相容 client；沒設定 base_url/model 就回 None（呼叫端據此處理）。
    max_retries=0：連不上時快速失敗，把錯誤如實回給上層。
    """
    if not settings.LLM_BASE_URL or not settings.LLM_MODEL:
        return None
    from openai import OpenAI
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "not-needed",  # 有些供應商（如 Ollama）不檢查金鑰
        timeout=_TIMEOUT_SEC,
        max_retries=0,
    )


def complete(client, messages: list, max_tokens: int = 1024, temperature: float = 0.7) -> str:
    """呼叫 LLM，回傳純文字回覆。"""
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def friendly_err(e: Exception) -> str:
    """把底層錯誤轉成新手看得懂的提示（特別是連不上 Ollama 的情況）。"""
    msg = str(e)
    low = msg.lower()
    if "connect" in low or "refused" in low or "connection" in low:
        return (
            "連不上 LLM 服務。若用預設的本機 Ollama：請先安裝並啟動（執行 `ollama serve`），"
            f"且已下載模型（`ollama pull {settings.LLM_MODEL}`）。"
            f"（原始錯誤：{msg}）"
        )
    return f"LLM 呼叫失敗：{msg}"
