"""
多年 OHLCV 本機快取（Phase 11 step-02）
=========================================
讓「整個歷史」回測跑得起來，又不每次都向 Alpaca / yfinance 重抓。
包在 `market_data.get_bars(symbol, days, source)` 的**外層**：缺的區間才補抓、
抓回來寫進本機快取；已有的區間命中快取、不重打外部 API。

設計重點（對齊 step-02 藍圖的鐵則）：
- **只包外層、不改底層**：唯一抓取來源仍是 `market_data.get_bars`，cache 不繞過它、
  不改它的簽章（維持單一抓取路徑、好除錯）。
- **不可成為偷看未來的後門**：回傳區間嚴格 ⊆ 請求區間（`_slice` 砍掉請求結束日之後的列）。
- **缺口判定保守、不被假日騙**：freshness 看「**已涵蓋的請求區間**」（sidecar meta），
  不看「最後一根 bar 的日期」。否則週末 / 假日 / 停牌時最後一根恆早於 today，
  會被誤判成缺口而**無限重抓**（DoD「第二次同請求 0 次 API」就破了）。
- **不同 source 不混存**：alpaca / yfinance 同 symbol 值可能不同 → 路徑按 {source}/{symbol} 分開。

存成 parquet（欄式、壓縮、pandas 原生）放 `BAR_CACHE_DIR`（預設 data/cache/bars，gitignore）。
旁邊放一個 `{symbol}.meta.json` 記「已涵蓋的請求區間」。

★ today 可注入：預設今天（date.today()），測試傳固定日期 → 缺口邏輯有確定性
  （仿 step-01 get_macro_series 的 as_of 縫）。
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from backend.config import settings
from backend.services import market_data


def _cache_paths(source: str, symbol: str) -> Tuple[Path, Path]:
    """回 (parquet 路徑, meta.json 路徑)。按 {source}/{symbol} 分開存，不混存。"""
    base = Path(settings.BAR_CACHE_DIR) / source.lower()
    symbol = symbol.upper()
    return base / f"{symbol}.parquet", base / f"{symbol}.meta.json"


def _read_cache(source: str, symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[dict]]:
    """
    讀本機快取。回 (bars, cov)；沒有快取（parquet 或 meta 任一缺）→ (None, None)。
    cov = {"covered_start": date, "covered_end": date}（已涵蓋的請求區間）。
    """
    parquet_path, meta_path = _cache_paths(source, symbol)
    if not parquet_path.exists() or not meta_path.exists():
        return None, None
    bars = pd.read_parquet(parquet_path)
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    cov = {
        "covered_start": _parse_iso(raw["covered_start"]),
        "covered_end": _parse_iso(raw["covered_end"]),
    }
    return bars, cov


def _write_cache(
    source: str, symbol: str, bars: pd.DataFrame, cov_start: date, cov_end: date
) -> None:
    """寫回 parquet + meta.json（自動建目錄）。"""
    parquet_path, meta_path = _cache_paths(source, symbol)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(parquet_path, index=False)
    meta_path.write_text(
        json.dumps(
            {"covered_start": cov_start.isoformat(), "covered_end": cov_end.isoformat()}
        ),
        encoding="utf-8",
    )


def _parse_iso(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _merge(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """
    合併兩段 K 線：去重（同 timestamp 保最新一筆，讓重抓的修正值勝出）、依時間升冪、重設索引。
    任一段為空都安全（concat 會略過空 df）。
    """
    frames = [df for df in (a, b) if df is not None and not df.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = (
        merged.drop_duplicates(subset="timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return merged


def _slice(df: pd.DataFrame, req_start: date, req_end: date) -> pd.DataFrame:
    """
    只回 req_start <= bar 日期 <= req_end 的列（嚴格 ⊆ 請求區間，不洩漏請求結束日之後的資料）。
    用 .dt.date 比對 → tz-agnostic（alpaca 可能帶時區、yfinance 不帶，都吃得下）。
    """
    if df is None or df.empty or "timestamp" not in df.columns:
        return df if df is not None else pd.DataFrame()
    bar_dates = pd.to_datetime(df["timestamp"]).dt.date
    mask = (bar_dates >= req_start) & (bar_dates <= req_end)
    return df[mask].reset_index(drop=True)


def get_bars_cached(
    symbol: str, days: int = 60, source: str = "alpaca", today: Optional[date] = None
) -> pd.DataFrame:
    """
    帶本機快取版的 get_bars：請求最近 `days` 天的日 K，缺口才補抓、其餘命中快取。

    :param symbol: 股票代號
    :param days: 往前抓幾天（日曆天）
    :param source: 資料源（"alpaca" / "yfinance"），快取按 source 分開存
    :param today: 「今天」基準（測試可注入固定日期；預設 date.today()）
    :return: 含 open/high/low/close/volume/timestamp 的 DataFrame（嚴格落在請求區間內、升冪）
    """
    today = today or date.today()
    req_start = today - timedelta(days=days)
    req_end = today

    bars, cov = _read_cache(source, symbol)

    # 1) 完全沒有快取 → 抓一次、寫出、回切片
    if bars is None:
        fetched = market_data.get_bars(symbol, days=days, source=source)
        _write_cache(source, symbol, fetched, req_start, req_end)
        return _slice(fetched, req_start, req_end)

    cov_start = cov["covered_start"]
    cov_end = cov["covered_end"]
    need_head = req_start < cov_start  # 請求比已涵蓋更早 → 頭缺口
    need_tail = req_end > cov_end      # 請求比已涵蓋更晚 → 尾缺口

    # 2) 請求區間已被涵蓋 → 全命中、0 次外部 API
    if not need_head and not need_tail:
        return _slice(bars, req_start, req_end)

    # 3) 補缺口（只補沒涵蓋到的那段）
    if need_tail:
        # 尾缺口：抓「已涵蓋結束日 → today」這段（days-API 由 today 往回抓，剛好蓋到）
        tail_days = (req_end - cov_end).days
        tail = market_data.get_bars(symbol, days=tail_days, source=source)
        bars = _merge(bars, tail)
    if need_head:
        # 頭缺口：days-API 只能由 today 往回抓 → 抓滿整段 days，新舊去重後即補上更早的列
        head = market_data.get_bars(symbol, days=days, source=source)
        bars = _merge(bars, head)

    _write_cache(
        source, symbol, bars, min(req_start, cov_start), max(req_end, cov_end)
    )
    return _slice(bars, req_start, req_end)


def get_bars_cached_multi(
    symbols: list[str], days: int = 60, source: str = "alpaca", today: Optional[date] = None
) -> dict[str, pd.DataFrame]:
    """
    批次版 get_bars_cached：逐檔查快取，只把「有缺口的檔」收集起來批次補抓
    （最多 2 次 HTTP：一次補「整段」桶、一次補「尾缺口」桶），再分別寫回快取。

    每檔的缺口判定 / 合併 / 切片與單檔版同義（重用同一組 _read_cache/_write_cache/
    _merge/_slice），所以結果與逐檔呼叫 get_bars_cached 一致——只是傳輸層批次化。
    批次抓取失敗時退回單檔舊路徑（網路抖動不全滅）；單檔也失敗回空 DataFrame。

    :return: {symbol: DataFrame}，key 必在（抓不到的檔是空 DataFrame）。
    """
    today = today or date.today()
    req_start = today - timedelta(days=days)
    req_end = today

    result: dict[str, pd.DataFrame] = {}
    cached: dict[str, tuple] = {}   # 有快取但有缺口的檔 → (bars, cov)，merge 用
    need_full: list[str] = []       # 無快取 / 頭缺口 → 抓滿整段 days
    need_tail: dict[str, int] = {}  # 只有尾缺口 → {symbol: tail_days}

    # 1) 逐檔讀快取、分桶（這段純磁碟、不打網路）
    for sym in dict.fromkeys(s.upper() for s in symbols):
        bars, cov = _read_cache(source, sym)
        if bars is None:
            need_full.append(sym)  # 完全沒快取 → 抓滿整段
            continue
        need_head = req_start < cov["covered_start"]
        has_tail_gap = req_end > cov["covered_end"]
        if not need_head and not has_tail_gap:
            result[sym] = _slice(bars, req_start, req_end)  # 全命中，0 次 API
        elif need_head:
            # 頭缺口：days-API 只能由 today 往回抓 → 抓滿整段再 merge 去重（同單檔版）
            need_full.append(sym)
            cached[sym] = (bars, cov)
        else:
            need_tail[sym] = (req_end - cov["covered_end"]).days
            cached[sym] = (bars, cov)

    def _finish(sym: str, fetched: Optional[pd.DataFrame]) -> None:
        """合併補抓結果、寫快取、放進 result。fetched=None ＝批次失敗 → 退單檔舊路徑。"""
        if fetched is None:
            try:
                result[sym] = get_bars_cached(sym, days=days, source=source, today=today)
            except Exception:
                result[sym] = pd.DataFrame()  # 單檔也失敗 → 空 df，不拖垮整批
            return
        old = cached.get(sym)
        if old is None:
            # 完全沒快取的首抓：直接寫出（同單檔版分支 1）
            _write_cache(source, sym, fetched, req_start, req_end)
            result[sym] = _slice(fetched, req_start, req_end)
            return
        bars, cov = old
        merged = _merge(bars, fetched)
        _write_cache(
            source, sym, merged,
            min(req_start, cov["covered_start"]), max(req_end, cov["covered_end"]),
        )
        result[sym] = _slice(merged, req_start, req_end)

    def _fetch_batch(syms: list[str], fetch_days: int) -> dict:
        """批次抓一桶；整批失敗回 {} → _finish 收到 None 走單檔 fallback。"""
        try:
            return market_data.get_bars_multi(syms, days=fetch_days, source=source)
        except Exception:
            return {}

    # 2) 批次補抓（每桶一次 HTTP）
    if need_full:
        fetched = _fetch_batch(need_full, days)
        for sym in need_full:
            _finish(sym, fetched.get(sym) if fetched else None)
    if need_tail:
        # 整桶用「最大尾缺口」天數抓：多抓幾天無害——_merge 按 timestamp 去重
        # （重抓的修正值勝出）、_slice 保證回傳嚴格 ⊆ 請求區間，不會偷看未來。
        fetched = _fetch_batch(list(need_tail), max(need_tail.values()))
        for sym in need_tail:
            _finish(sym, fetched.get(sym) if fetched else None)

    return result
