"""
層驗證 harness（用 step-07 驗證 step-03~06 各層有沒有加分）── Phase 7 收尾
==========================================================================
step-07 的 validation.py 備好了底層工具（walk-forward 切分 + is_layer_worth_it），這支把
Phase 7 後面幾層真的接上去做「baseline（不加層）vs candidate（加層）」的樣本外比較，誠實判定
每層「加了有沒有在 OOS 贏過不加」。**加不了分的層就該砍**——這正是 step-07 文件的鐵律：
這套框架是用來「殺掉沒用的層」，不是美化績效。

四層怎麼驗（誠實分級）：
- step-05 meta：baseline=策略原始訊號；candidate=同策略 + should_take 過濾進場。指標=每 fold EV。✅乾淨
- step-03 adaptive：baseline=該 fold 訓練段 EV 最高的「單一固定策略」；candidate=自適應（對照表由
  訓練段建）。指標=每 fold EV。✅（較重）
- step-04 kelly：凱利是「下注比例」，不改單筆 EV，改的是複利成長。指標=同一串已實現報酬下，
  固定比例 vs 凱利比例的終值。⚠️用報酬不用 EV。
- step-06 event：**無歷史逐時點情緒**，事件→價格回測必洩漏未來 → 不納入 OOS EV 閘，誠實標記
  「不可驗證，僅當風險煞車」。❌不產生假數字。

關鍵設計：把層當「包裝策略」塞進既有含成本回測路徑（_run_on_df 只要求 generate_signal），
不動 _simulate_from_signals。

重用：validation.walk_forward_splits / is_layer_worth_it、backtest_engine._run_on_df、
regime_features / regime / strategy_selector.build_map_from_df + select_strategy、
meta_label.should_take、sizing.kelly_fraction、market_data.get_bars。
"""

import pandas as pd

from backend.config import settings
from backend.services import market_data
from backend.services.backtest_engine import _run_on_df
from backend.services.macro_features import attach_macro_features
from backend.services.meta_label import should_take
from backend.services.orderflow_proxy import compute_orderflow
from backend.services.regime import classify_regime
from backend.services.regime_features import compute_features
from backend.services.sizing import kelly_fraction
from backend.services.strategy_selector import build_map_from_df, select_strategy
from backend.services.validation import is_layer_worth_it, walk_forward_splits
from backend.strategies import STRATEGY_REGISTRY, Signal, get_strategy

_INITIAL_CASH = 10000.0

# 環境特徵欄（step-04 features 管線傳給訊號層的欄位）：
# macro 6 欄（同 macro_features._FEATURE_COLS）+ orderflow 4 欄（同 compute_orderflow 產出）。
_MACRO_FEATURE_COLS = [
    "fed_funds_level", "fed_funds_3m_chg", "unemployment_trend",
    "cpi_yoy", "yield_curve", "vix_level",
]
_ORDERFLOW_COLS = ["buy_vol_proxy", "sell_vol_proxy", "net_pressure", "pressure_ratio"]
_ENV_FEATURE_COLS = _MACRO_FEATURE_COLS + _ORDERFLOW_COLS


def _cost():
    """回（手續費, 滑價）bps，與正式回測同一組設定。"""
    return settings.BACKTEST_COMMISSION_BPS, settings.BACKTEST_SLIPPAGE_BPS


# ============================================================
# 包裝策略：把「加的層」塞進既有回測路徑（generate_signal 介面）
# ============================================================
class MetaFilteredStrategy:
    """step-05：一級策略產訊號後，BUY 再過 meta 二級過濾；否決則縮回 HOLD。"""

    def __init__(self, base):
        self.base = base

    def generate_signal(self, df):
        sig, reason = self.base.generate_signal(df)
        if sig == Signal.BUY:
            feats = compute_features(df)
            regime = classify_regime(feats)
            take, conf = should_take(sig, feats, regime)
            if not take:
                return Signal.HOLD, f"meta 二級否決（信心 {conf:.2f}）"
        return sig, reason


class AdaptiveMappedStrategy:
    """step-03：用「已建好的對照表」逐根挑策略再委派。

    無可信策略時 **退回 best-fixed（穩健預設）而非 HOLD**：meta-strategy 在沒把握的狀態
    不該去坐現金、白白丟掉基準的 edge，而該用「整體最佳固定策略」當地板。如此 candidate
    只在「有把握更好的狀態」才偏離 baseline，驗證的就是純粹的『狀態切換有沒有加分』。
    fallback_key=None（沒有 best-fixed 可退）時才退回 HOLD（保守觀望）。
    """

    def __init__(self, regime_map: dict, fallback_key: str | None = None):
        self.regime_map = regime_map
        self.fallback_key = fallback_key

    def generate_signal(self, df):
        feats = compute_features(df)
        pick = select_strategy(feats, self.regime_map)
        if pick["fallback"] or not pick["strategy"]:
            if self.fallback_key is None:
                return Signal.HOLD, f"自適應 {pick['regime']} 無可信策略且無預設"
            return get_strategy(self.fallback_key, {}).generate_signal(df)
        strat = get_strategy(pick["strategy"], pick["params"])
        return strat.generate_signal(df)


class MacroOverlayStrategy:
    """step-11（Phase 11）：環境風險煞車。

    base 策略出 BUY 時，若 a-priori 固定門檻判「risk-off」（恐慌 / 衰退預警 / 賣壓），
    把 BUY 縮回 HOLD——**只煞車、不猜方向**（對齊 Phase 11 鐵則 3 + step-06 event 精神）。
    SELL / HOLD 一律原樣放行（煞車不該擋出場）。

    讀的是 step-04 features 管線併進訊號層 df 的環境特徵欄；缺欄 / NaN（沒 FRED 資料）
    → 視為「不煞車」，candidate 退化成 baseline（優雅降級，誠實顯示「無加分」）。
    """

    def __init__(self, base):
        self.base = base

    def generate_signal(self, df):
        sig, reason = self.base.generate_signal(df)
        if sig == Signal.BUY and _macro_risk_off(df.iloc[-1]):
            return Signal.HOLD, "環境 risk-off 煞車"
        return sig, reason


def _macro_risk_off(row) -> bool:
    """a-priori 固定可解釋門檻（**不在任何資料上 fit**）；任一觸發即 risk-off。

    NaN / 缺欄一律當「未觸發」（公布前沒值、沒 FRED 資料時不亂煞車）。
    - vix_level > 30          ：恐慌（risk-off）
    - yield_curve < 0         ：殖利率倒掛（衰退預警）
    - unemployment_trend > 0  ：失業率上升（衰退傾向）
    - pressure_ratio < 0.5    ：賣壓 > 買壓（orderflow 代理偏空）
    """
    def _hot(key: str, lo: float | None, hi: float | None) -> bool:
        v = row.get(key)
        if v is None or pd.isna(v):
            return False
        if lo is not None and v > lo:
            return True
        if hi is not None and v < hi:
            return True
        return False

    return (
        _hot("vix_level", lo=30.0, hi=None)
        or _hot("yield_curve", lo=None, hi=0.0)
        or _hot("unemployment_trend", lo=0.0, hi=None)
        or _hot("pressure_ratio", lo=None, hi=0.5)
    )


def _build_features(df, db) -> pd.DataFrame:
    """組環境特徵欄（macro + orderflow），回「只含特徵欄」的 DataFrame 餵給 _run_on_df(features=...)。

    db=None（或沒 FRED 資料）→ macro 欄全 NaN（優雅降級）；orderflow 只要有 close/volume 就算得出。
    保證回傳含 _ENV_FEATURE_COLS 全部欄（缺的補 NaN），與 df 等長、位置對齊。
    """
    if db is not None:
        enriched = attach_macro_features(df, db)
    else:
        enriched = df.copy()
        for c in _MACRO_FEATURE_COLS:
            enriched[c] = float("nan")
    enriched = compute_orderflow(enriched)
    for c in _ENV_FEATURE_COLS:
        if c not in enriched.columns:
            enriched[c] = float("nan")
    return enriched[_ENV_FEATURE_COLS].reset_index(drop=True)


# ============================================================
# 小工具
# ============================================================
def _ev_on(strategy, test_df) -> float:
    """在測試段跑含成本回測，回期望值 EV。"""
    comm, slip = _cost()
    return _run_on_df(strategy, test_df, _INITIAL_CASH, commission_bps=comm, slippage_bps=slip)["expected_value"]


def _best_fixed_key(train_df) -> str | None:
    """挑「訓練段 EV 最高」的單一固定策略當 baseline 比較對象（在 train 段決定，不偷看 test）。"""
    comm, slip = _cost()
    best_key, best_ev = None, None
    for key in STRATEGY_REGISTRY:
        ev = _run_on_df(get_strategy(key, {}), train_df, _INITIAL_CASH,
                        commission_bps=comm, slippage_bps=slip)["expected_value"]
        if best_ev is None or ev > best_ev:
            best_ev, best_key = ev, key
    return best_key


def _roundtrip_returns(trades: list) -> list[float]:
    """把交易紀錄配對成 round-trip，回每筆「占投入本金的報酬率」（profit / 進場成本）。"""
    rs, buy = [], None
    for t in trades:
        if t["side"] == "buy":
            buy = t
        elif t["side"] == "sell" and buy is not None:
            cost = buy["price"] * buy["qty"]
            if cost > 0:
                rs.append(t.get("profit", 0.0) / cost)
            buy = None
    return rs


def _terminal_return(returns: list[float], fraction: float) -> float:
    """用固定下注比例 fraction 對一串報酬做複利，回終值報酬（∏(1+f·r) − 1）。"""
    eq = 1.0
    for r in returns:
        eq *= 1.0 + fraction * r
    return eq - 1.0


# ============================================================
# 各層驗證（回 baseline/candidate 兩串 + is_layer_worth_it 判定）
# ============================================================
def validate_meta_layer(df) -> dict:
    """step-05：每 fold × 每策略，比「原始訊號 EV」與「meta 過濾後 EV」。"""
    comm, slip = _cost()
    base_oos, cand_oos = [], []
    for fold in walk_forward_splits(len(df)):
        test = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        for key in STRATEGY_REGISTRY:
            b = _run_on_df(get_strategy(key, {}), test, _INITIAL_CASH, commission_bps=comm, slippage_bps=slip)
            c = _run_on_df(MetaFilteredStrategy(get_strategy(key, {})), test, _INITIAL_CASH,
                           commission_bps=comm, slippage_bps=slip)
            # 兩邊都沒交易 → meta 沒東西可過濾，跳過（不灌 0 進樣本）
            if b["num_round_trips"] == 0 and c["num_round_trips"] == 0:
                continue
            base_oos.append(b["expected_value"])
            cand_oos.append(c["expected_value"])
    return {"layer": "step-05 meta-labeling", "baseline_oos": base_oos, "candidate_oos": cand_oos,
            "verdict": is_layer_worth_it(base_oos, cand_oos)}


def validate_adaptive_layer(df) -> dict:
    """step-03：每 fold 比「訓練段最佳固定策略」與「自適應選策略」在測試段的 EV。"""
    base_oos, cand_oos = [], []
    for fold in walk_forward_splits(len(df)):
        train = df.iloc[fold["train_start"]: fold["train_end"]].reset_index(drop=True)
        test = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        best_key = _best_fixed_key(train)
        if best_key is None:
            continue
        regime_map = build_map_from_df(train, initial_cash=_INITIAL_CASH)
        base_oos.append(_ev_on(get_strategy(best_key, {}), test))
        # 無可信狀態時退回 best_key（同 baseline 的地板），驗純粹狀態切換的增益
        cand_oos.append(_ev_on(AdaptiveMappedStrategy(regime_map, fallback_key=best_key), test))
    return {"layer": "step-03 adaptive-selection", "baseline_oos": base_oos, "candidate_oos": cand_oos,
            "verdict": is_layer_worth_it(base_oos, cand_oos)}


def _kelly_fraction_from_returns(rs: list[float]) -> float | None:
    """從一串 round-trip 報酬估 W/R → 分數凱利比例。樣本不足 → None（不可信）。"""
    if len(rs) < settings.KELLY_MIN_ROUND_TRIPS:
        return None
    wins = [r for r in rs if r > 0]
    losses = [-r for r in rs if r < 0]
    w = len(wins) / len(rs)
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    return kelly_fraction(w, avg_win, avg_loss)


def validate_kelly_layer(df) -> dict:
    """step-04：OOS-honest 凱利驗證。

    舊版在「同一段測試窗」上同時估 W/R 又複利 → 既看未來（in-sample 凱利）又因 60 根測試窗
    湊不到 KELLY_MIN_ROUND_TRIPS 而每 fold 全 skip（folds=0，根本沒驗到）。

    新版分離訓練/測試：
      - 在**訓練段**估凱利比例（180 根較易湊到 ≥KELLY_MIN_ROUND_TRIPS，且不偷看測試）。
      - 把「固定比例」與「凱利比例」套到**測試段**的已實現報酬流複利，比終值報酬。
      - 測試段只需 ≥1 筆 round-trip（有報酬可複利即可）。
    如此凱利比例是樣本外套用，且測試不再保證 skip。
    """
    comm, slip = _cost()
    f_fixed = settings.KELLY_MAX_FRACTION  # 樸素的固定下注比例當 baseline
    base_oos, cand_oos = [], []
    for fold in walk_forward_splits(len(df)):
        # 凱利估 W/R 需足量 round-trip；固定 180 根 train 常湊不到 → 用「測試前全段」
        # 的擴張窗（anchored walk-forward）估比例。仍嚴格 OOS（只用 test 之前的資料）。
        train = df.iloc[0: fold["test_start"]].reset_index(drop=True)
        test = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        best_key = _best_fixed_key(train)
        if best_key is None:
            continue
        # 訓練段估凱利比例（OOS：比例來自 train，不偷看 test）
        train_trades = _run_on_df(get_strategy(best_key, {}), train, _INITIAL_CASH,
                                  commission_bps=comm, slippage_bps=slip)["trades"]
        f_kelly = _kelly_fraction_from_returns(_roundtrip_returns(train_trades))
        if f_kelly is None:  # 訓練段樣本不足 → W/R 不可信，跳過該 fold
            continue
        # 測試段已實現報酬流，套兩種比例複利比終值
        test_trades = _run_on_df(get_strategy(best_key, {}), test, _INITIAL_CASH,
                                 commission_bps=comm, slippage_bps=slip)["trades"]
        rs_test = _roundtrip_returns(test_trades)
        if not rs_test:  # 測試段沒交易 → 沒東西可複利，跳過
            continue
        base_oos.append(_terminal_return(rs_test, f_fixed))
        cand_oos.append(_terminal_return(rs_test, f_kelly))
    return {"layer": "step-04 kelly-sizing", "metric": "terminal_return",
            "baseline_oos": base_oos, "candidate_oos": cand_oos,
            "verdict": is_layer_worth_it(base_oos, cand_oos)}


def validate_macro_layer(df, db) -> dict:
    """step-11（Phase 11）：每 fold × 每策略，比「純價量 baseline」與「+環境覆蓋 candidate」的 EV。

    candidate 唯一差別 = 多吃 step-03 的 macro / 買賣壓特徵（透過 step-04 的 features 管線），
    並以 a-priori 固定門檻在 risk-off 時煞車進場。沒 FRED 資料時 candidate 退化成 baseline →
    improvement≈0 → worth=False（誠實標「無加分」）。
    """
    comm, slip = _cost()
    base_oos, cand_oos = [], []
    for fold in walk_forward_splits(len(df)):
        test = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        feats = _build_features(test, db)
        for key in STRATEGY_REGISTRY:
            b = _run_on_df(get_strategy(key, {}), test, _INITIAL_CASH,
                           commission_bps=comm, slippage_bps=slip)
            c = _run_on_df(MacroOverlayStrategy(get_strategy(key, {})), test, _INITIAL_CASH,
                           commission_bps=comm, slippage_bps=slip, features=feats)
            # 兩邊都沒交易 → 環境覆蓋沒東西可煞，跳過（不灌 0 進樣本）
            if b["num_round_trips"] == 0 and c["num_round_trips"] == 0:
                continue
            base_oos.append(b["expected_value"])
            cand_oos.append(c["expected_value"])
    return {"layer": "step-11 macro-overlay", "baseline_oos": base_oos, "candidate_oos": cand_oos,
            "verdict": is_layer_worth_it(base_oos, cand_oos)}


# step-06：誠實的「不可 OOS 驗證」結論（不產生假數字）
_EVENT_NOTE = {
    "layer": "step-06 event-risk",
    "validatable": False,
    "verdict": {"worth": None, "reason": (
        "無 point-in-time 情緒/事件歷史，任何『事件→價格』回測都會洩漏未來，故不納入 OOS EV 閘。"
        "定位維持『風險煞車』（降風險、不猜方向）：負面期降曝險、平時不拖累；非 alpha 層，不以 EV 證明。"
    )},
}


def validate_symbol(df, db=None) -> dict:
    """對單一檔的 K 線跑四層可驗證的層 + step-06 誠實註記。

    :param db: macro 層用的 DB session（取 FRED 序列做 point-in-time 對齊）；
               None → macro 特徵全 NaN，candidate 退化成 baseline（優雅降級）。
    """
    return {
        "meta": validate_meta_layer(df),
        "adaptive": validate_adaptive_layer(df),
        "kelly": validate_kelly_layer(df),
        "macro": validate_macro_layer(df, db),
        "event": dict(_EVENT_NOTE),
    }


def validate_layers(symbols=None, source: str = "yfinance", days: int = 730) -> dict:
    """
    跨多檔跑層驗證，把各檔各 fold 的指標**池化**後再判定（樣本更足、更可信）。

    :param symbols: 標的清單；None → 讀 settings.SCREENER_WATCHLIST。
    :param source: 資料源（預設 yfinance，免費免金鑰）。
    :param days: 每檔往前抓幾天（預設 730，夠切出多個 walk-forward fold）。
    :return: {"symbols", "skipped", per_layer 池化 verdict, "event": 誠實註記}
    """
    if symbols is None:
        from backend.services import screener
        symbols = screener.parse_watchlist(settings.SCREENER_WATCHLIST)

    # macro 層要 DB session 取 FRED 序列做 point-in-time 對齊；開一次、用完關。
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        pools = {"meta": ([], []), "adaptive": ([], []), "kelly": ([], []), "macro": ([], [])}
        used, skipped = [], []
        for sym in symbols:
            try:
                df = market_data.get_bars(sym.upper(), days=days, source=source)
            except Exception as e:
                skipped.append({"symbol": sym, "reason": str(e)})
                continue
            if df.empty or len(df) < settings.VALIDATION_TRAIN_WINDOW + settings.VALIDATION_TEST_WINDOW:
                skipped.append({"symbol": sym, "reason": "資料不足，湊不出 fold"})
                continue
            res = validate_symbol(df, db)
            for layer in pools:
                pools[layer][0].extend(res[layer]["baseline_oos"])
                pools[layer][1].extend(res[layer]["candidate_oos"])
            used.append(sym.upper())
    finally:
        db.close()

    out = {"symbols": used, "skipped": skipped, "event": dict(_EVENT_NOTE)}
    layer_names = {"meta": "step-05 meta-labeling", "adaptive": "step-03 adaptive-selection",
                   "kelly": "step-04 kelly-sizing", "macro": "step-11 macro-overlay"}
    for layer, (base_oos, cand_oos) in pools.items():
        out[layer] = {"layer": layer_names[layer], "baseline_oos": base_oos, "candidate_oos": cand_oos,
                      "verdict": is_layer_worth_it(base_oos, cand_oos)}
    return out
