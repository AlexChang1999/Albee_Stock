"""
狀態 → 策略自適應選擇（Adaptive Strategy Selection）── Phase 7 step-03
======================================================================
回答：「**現在是 X 狀態，歷史上 X 狀態時哪個策略的 OOS EV 最高？就用它。**」
這把願景「A 股爆量滯漲 → 推斷出該用 C 策略」真正實現。

上層不直接交易，而是「挑哪個下層策略來交易」（meta-strategy）。

核心流程：
  build_regime_strategy_map(symbol)：離線。跑回測 + 給每根 K 棒貼狀態標籤，
    把每筆 round-trip 的盈虧歸到「進場當時的狀態」，算出每個狀態下各策略的 EV / 勝率，
    建一張「狀態 → 最佳策略」對照表。
  select_strategy(features, map)：線上。算當下狀態 → 查表 → 回該狀態最佳策略。

⚠️ 這步最危險（過擬合重災區），守三條防線：
  1. **對照表用 OOS 段建**：只看樣本外（optimizer.split_train_test 的 test 段），
     不在整段歷史上挑最佳（呼應 Phase 6 step-04）。
  2. **最小樣本門檻**：切子樣本後每狀態交易筆數會驟減。某狀態交易筆數 < REGIME_MIN_SAMPLE
     就不信任其統計，退回保守預設（不亂下注）。防「12 筆勝率 75% 是運氣」。
  3. **含成本回測**：走 _run_on_df（手續費 / 滑價 / 隔日成交），EV 才誠實。

⚠️ 這層的 edge **必須被證明**：自適應是否真的在 OOS 上贏過「單一最佳策略」，
   要靠 step-07 的驗證框架判定；贏不過就該砍掉這層（不要 vibe slop）。本檔只落地「機制」，
   不宣稱已證明有效——預設關（bot.adaptive=False），且狀態無可信策略時保守觀望。
"""

from backend.config import settings
from backend.services import market_data
from backend.services.backtest_engine import _run_on_df
from backend.services.optimizer import split_train_test
from backend.services.regime import classify_regime
from backend.services.regime_features import compute_features
from backend.strategies import STRATEGY_REGISTRY, get_strategy


def _label_regimes(df) -> list[str]:
    """對每根 K 棒貼「當時的狀態標籤」（walk-forward：第 i 根只看到第 i 根為止）。

    與回測同款無未來函數紀律：用 df.iloc[:i+1] 算特徵再分類，不偷看未來。
    """
    return [classify_regime(compute_features(df.iloc[: i + 1])) for i in range(len(df))]


def _bar_index_resolver(df):
    """回一個「trade 的 date 字串 → bar 索引」的查詢函式。

    backtest_engine 的 trade date：有 timestamp 欄時是 'YYYY-MM-DD'，否則是 str(i)。
    兩種都支援，查不到回 None。
    """
    if "timestamp" in df.columns:
        lookup = {str(ts)[:10]: i for i, ts in enumerate(df["timestamp"])}

        def resolve(date: str):
            return lookup.get(date)
    else:
        def resolve(date: str):
            try:
                return int(date)
            except (TypeError, ValueError):
                return None

    return resolve


def _profits_by_regime(trades: list, regimes: list[str], resolve) -> dict[str, list[float]]:
    """把每筆 round-trip 的盈虧，歸到「進場(buy)當時的狀態」。

    round-trip = 一次 buy 配一次 sell；sell 才帶 profit。用 buy 的成交 bar 的狀態當歸因，
    因為「決定要不要進場」是看當時的市場狀態。
    """
    by_regime: dict[str, list[float]] = {}
    pending_buy_regime = None
    for t in trades:
        bar = resolve(t.get("date"))
        if t["side"] == "buy":
            # 記住這筆買進當時的狀態（bar 解析不出來就記 None，對應的 sell 會被跳過）
            pending_buy_regime = regimes[bar] if bar is not None and 0 <= bar < len(regimes) else None
        elif t["side"] == "sell" and pending_buy_regime is not None:
            by_regime.setdefault(pending_buy_regime, []).append(float(t.get("profit", 0.0)))
            pending_buy_regime = None
    return by_regime


def build_regime_strategy_map(
    symbol: str,
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str | None = None,
) -> dict:
    """
    建「狀態 → 最佳策略對照表」（離線計算，建議快取，別每次線上重算）。

    對每個策略（用各自預設參數）在 **OOS 測試段** 跑含成本回測，把每筆交易盈虧歸到
    進場當時的狀態，算每狀態下各策略的 EV / 勝率 / 筆數；每狀態挑「筆數達門檻且 EV>0」
    中 EV 最高者。無人達標 → 該狀態回 None（保守觀望）。

    :return: {
        "symbol", "oos_bars", "min_sample",
        "regimes": { 狀態: {"strategy", "params", "expected_value", "win_rate_pct",
                            "num_round_trips"}  或  None（無可信策略）},
        "stats": { 狀態: { 策略: {ev, win_rate_pct, n} } }  # 完整明細，供查驗
      }
    """
    symbol = symbol.upper()
    src = source or settings.DATA_SOURCE

    df = market_data.get_bars(symbol, days=days, source=src)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    # 對照表只用樣本外（OOS）段建，避免在整段歷史上挑最佳（過擬合）
    _, test_df = split_train_test(df, settings.OOS_TEST_RATIO)
    test_df = test_df.reset_index(drop=True)

    result = build_map_from_df(test_df, initial_cash=initial_cash)
    result["symbol"] = symbol
    return result


def build_map_from_df(df, initial_cash: float = 10000.0) -> dict:
    """
    在「一段已備好的 K 線」上建狀態→最佳策略對照表（純計算，不抓資料、不再切分）。

    從 build_regime_strategy_map 抽出的核心：呼叫端負責決定要在哪一段建（如整段的 OOS 測試段、
    或 walk-forward 每個 fold 的訓練段），本函式只做「貼狀態 + 跑各策略 + 歸因 + 挑冠軍」。
    含成本回測（手續費/滑價/隔日成交），EV 才誠實。

    :param df: 要建表的 K 線段（呼叫端應已 reset_index）。
    :return: {"oos_bars", "min_sample", "regimes": {狀態: 冠軍 dict 或 None}, "stats": 完整明細}
             （不含 symbol；build_regime_strategy_map 會補上）。
    """
    commission_bps = settings.BACKTEST_COMMISSION_BPS
    slippage_bps = settings.BACKTEST_SLIPPAGE_BPS
    min_sample = settings.REGIME_MIN_SAMPLE

    regimes = _label_regimes(df)
    resolve = _bar_index_resolver(df)

    # stats[regime][strategy] = {ev, win_rate_pct, n}
    stats: dict[str, dict[str, dict]] = {}
    for strategy_key in STRATEGY_REGISTRY:
        result = _run_on_df(
            get_strategy(strategy_key, {}), df, initial_cash,
            commission_bps=commission_bps, slippage_bps=slippage_bps,
        )
        by_regime = _profits_by_regime(result["trades"], regimes, resolve)
        for regime, profits in by_regime.items():
            n = len(profits)
            if n == 0:
                continue
            ev = sum(profits) / n
            wins = sum(1 for p in profits if p > 0)
            stats.setdefault(regime, {})[strategy_key] = {
                "ev": round(ev, 2),
                "win_rate_pct": round(wins / n * 100, 2),
                "n": n,
            }

    # 每狀態挑冠軍：筆數達門檻且 EV>0 中 EV 最高者；無人達標 → None（保守）
    regime_map: dict[str, dict | None] = {}
    for regime, per_strategy in stats.items():
        qualified = [
            (k, s) for k, s in per_strategy.items()
            if s["n"] >= min_sample and s["ev"] > 0
        ]
        if not qualified:
            regime_map[regime] = None
            continue
        best_key, best = max(qualified, key=lambda kv: kv[1]["ev"])
        regime_map[regime] = {
            "strategy": best_key,
            "params": {},
            "expected_value": best["ev"],
            "win_rate_pct": best["win_rate_pct"],
            "num_round_trips": best["n"],
        }

    return {
        "oos_bars": len(df),
        "min_sample": min_sample,
        "regimes": regime_map,
        "stats": stats,
    }


def select_strategy(features: dict, regime_map: dict) -> dict:
    """
    線上：依當下特徵算狀態 → 查對照表 → 回該狀態最佳策略。

    狀態未知 / 不在表內 / 該狀態無可信策略（None）→ 保守退回「不出手」
    （strategy=None，呼叫端應觀望，不亂下注）。

    :param features: regime_features.compute_features(df) 的輸出
    :param regime_map: build_regime_strategy_map 的輸出
    :return: {
        "regime", "strategy"(可能 None), "params",
        "expected_value", "win_rate_pct", "num_round_trips",
        "fallback"(bool, True=退回保守觀望)
      }
    """
    regime = classify_regime(features)
    entry = (regime_map.get("regimes") or {}).get(regime)
    if entry is None:
        return {
            "regime": regime,
            "strategy": None,
            "params": {},
            "expected_value": None,
            "win_rate_pct": None,
            "num_round_trips": 0,
            "fallback": True,
        }
    return {
        "regime": regime,
        "strategy": entry["strategy"],
        "params": entry.get("params", {}),
        "expected_value": entry.get("expected_value"),
        "win_rate_pct": entry.get("win_rate_pct"),
        "num_round_trips": entry.get("num_round_trips", 0),
        "fallback": False,
    }


# ---- 線上用：對照表快取（離線建一次，線上重複查，別每輪重算）----
_MAP_CACHE: dict[str, dict] = {}


def get_regime_strategy_map(symbol: str, force: bool = False) -> dict:
    """取某標的的對照表；已建過就回快取，force=True 重建。

    對照表是「離線、較貴」的計算（要跑遍所有策略回測），所以快取在記憶體，
    線上選策略時重複查。需要更新（例如每日盤前）時呼叫 force=True 重建。
    """
    symbol = symbol.upper()
    if force or symbol not in _MAP_CACHE:
        _MAP_CACHE[symbol] = build_regime_strategy_map(symbol)
    return _MAP_CACHE[symbol]
