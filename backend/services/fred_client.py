"""
FRED 總經資料 client（聖路易聯準會 FRED API，免費）
====================================================
只負責「打 FRED 拿某序列的觀測值」這一件事，集中一處。仿 services/llm.py 的精神：
- 沒設 FRED_API_KEY → 視為未啟用，回 None（呼叫端據此優雅跳過，不崩、不阻斷其他功能）。
- 連不上 / 金鑰錯 / 格式異常 → best-effort 回 None，不讓外站問題拖垮系統。

FRED API 文件：https://fred.stlouisfed.org/docs/api/fred/series_observations.html
免費 API key 申請：https://fred.stlouisfed.org/docs/api/api_key.html
"""

from typing import Optional

import requests

from backend.config import settings

_FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT_SEC = 20
_USER_AGENT = "AlbeeStock/1.0 (+personal research; best-effort)"


def has_key() -> bool:
    """有沒有設定 FRED API key（沒設＝整個總經功能視為關閉）。"""
    return bool(settings.FRED_API_KEY)


def get_observations(
    series_id: str, start: Optional[str] = None, end: Optional[str] = None
) -> Optional[list]:
    """
    抓某 FRED 序列的觀測值。

    :param series_id: FRED 序列代號（如 PAYEMS、UNRATE、FEDFUNDS）。
    :param start: 起始日 YYYY-MM-DD（選用）。
    :param end: 結束日 YYYY-MM-DD（選用）。
    :return: [{"date": "2024-05-01", "value": 272.0}, ...]（已過濾缺值）；
             沒 key 或抓取失敗時回 None（best-effort，不拋例外）。
    """
    if not has_key():
        return None

    params = {
        "series_id": series_id,
        "api_key": settings.FRED_API_KEY,
        "file_type": "json",
    }
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end

    try:
        resp = requests.get(
            _FRED_OBS_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        # 連不上 / 金鑰錯 / 格式異常 → best-effort 回 None，不阻斷其他功能
        return None

    out = []
    for obs in payload.get("observations", []):
        raw = obs.get("value")
        # FRED 用 "." 表示該期缺值，跳過
        if raw in (None, "", "."):
            continue
        try:
            out.append({"date": obs["date"], "value": float(raw)})
        except (KeyError, ValueError):
            continue
    return out
