"""
蒙地卡羅壓力測試（bootstrap 重抽日報酬）
==========================================
回測只給你「歷史那一條」資金曲線；壓力測試回答的是：
「如果同樣的日報酬分布，換個順序重來一千次，會發生什麼？」

方法選擇：
- **採用 iid bootstrap**：從回測實際產生的日報酬中「有放回」隨機重抽，
  組成 N 條模擬路徑。不假設報酬呈常態分布（厚尾、偏態原樣保留），
  符合本專案「回測 = 實盤誠實估計」的原則。
- **捨棄 GBM（幾何布朗運動）**：GBM 假設報酬常態、波動率固定，
  會低估尾部風險（黑天鵝），與壓力測試的目的相反。
- **不用 antithetic variates（對偶變數法）**：那是對「對稱參數分布」
  （如常態隨機數取負號）的變異數減額技巧；經驗分布重抽沒有自然的
  「對偶樣本」，硬做會扭曲分布。N=1000 的 numpy 向量化只要毫秒級，
  不需要加速技巧。

限制（誠實註記）：iid 重抽會打散報酬的「自相關」（連跌行情的叢聚性），
對趨勢型策略的回撤可能略為低估；解讀分布時當「下界參考」而非保證。

純函式、無 DB、無連線；seed 可固定供測試重現。
"""

import numpy as np
import pandas as pd

# 樣本太少時 bootstrap 重抽只是噪音放大器，直接拒算
MIN_RETURNS = 30


def bootstrap_paths(daily_returns, n_paths: int = 1000, horizon: int | None = None,
                    seed: int | None = None) -> np.ndarray:
    """
    從日報酬序列 bootstrap 出 N 條模擬「累積淨值倍數」路徑。

    :param daily_returns: 日報酬率序列（list 或 pd.Series，returns_from_equity 的輸出）
    :param n_paths: 模擬路徑數
    :param horizon: 每條路徑的天數；None = 與原始序列等長
    :param seed: 隨機種子（給定則結果可重現）
    :return: shape=(n_paths, horizon) 的 ndarray，值為「相對初始資金的倍數」
             （第 t 天 = 前 t 筆重抽報酬的連乘）
    :raises ValueError: 日報酬少於 MIN_RETURNS 筆
    """
    rets = np.asarray(pd.Series(daily_returns).dropna(), dtype=float)
    if len(rets) < MIN_RETURNS:
        raise ValueError(f"日報酬僅 {len(rets)} 筆（< {MIN_RETURNS}），樣本太少不適合 bootstrap")
    if horizon is None:
        horizon = len(rets)
    rng = np.random.default_rng(seed)
    # 有放回重抽：每條路徑、每一天都從歷史日報酬隨機挑一筆
    sampled = rng.choice(rets, size=(n_paths, horizon), replace=True)
    # 累積淨值倍數 = (1+r1)(1+r2)...(1+rt)
    return np.cumprod(1.0 + sampled, axis=1)


def _max_drawdown_pct(paths: np.ndarray) -> np.ndarray:
    """逐路徑算最大回撤 %（正值）。paths shape=(n_paths, horizon)。"""
    running_max = np.maximum.accumulate(paths, axis=1)
    drawdown = 1.0 - paths / running_max
    return drawdown.max(axis=1) * 100


def stress_summary(daily_returns, initial_equity: float = 10000.0,
                   n_paths: int = 1000, seed: int | None = None,
                   drawdown_threshold_pct: float = 20.0,
                   ruin_threshold_pct: float = 50.0) -> dict:
    """
    跑 bootstrap 壓力測試，回傳分布統計（JSON-friendly dict，可直接回前端）。

    :param daily_returns: 日報酬率序列
    :param initial_equity: 初始資金（換算最終權益用）
    :param n_paths: 模擬路徑數
    :param seed: 隨機種子
    :param drawdown_threshold_pct: 「回撤超過 X%」的機率門檻
    :param ruin_threshold_pct: 「破產」定義 = 權益自峰值回撤超過此 %
    :raises ValueError: 日報酬筆數不足（由 bootstrap_paths 丟出）
    """
    paths = bootstrap_paths(daily_returns, n_paths=n_paths, seed=seed)
    final_equity = paths[:, -1] * initial_equity
    max_dd = _max_drawdown_pct(paths)

    rnd = lambda v: round(float(v), 2)
    return {
        "method": "bootstrap",          # 重抽歷史日報酬，非 GBM 參數模擬
        "n_paths": int(n_paths),
        "horizon_days": int(paths.shape[1]),
        "seed": seed,
        "initial_equity": rnd(initial_equity),
        # 最終權益分布（5/50/95 百分位：悲觀/中位/樂觀情境）
        "final_equity_p5": rnd(np.percentile(final_equity, 5)),
        "final_equity_p50": rnd(np.percentile(final_equity, 50)),
        "final_equity_p95": rnd(np.percentile(final_equity, 95)),
        # 最大回撤分布
        "max_drawdown_p50": rnd(np.percentile(max_dd, 50)),
        "max_drawdown_p95": rnd(np.percentile(max_dd, 95)),
        # 風險機率：N 條路徑中有多少比例觸發門檻
        "drawdown_threshold_pct": rnd(drawdown_threshold_pct),
        "prob_drawdown_exceeds_pct": rnd((max_dd > drawdown_threshold_pct).mean() * 100),
        "ruin_threshold_pct": rnd(ruin_threshold_pct),
        "prob_ruin": rnd((max_dd > ruin_threshold_pct).mean() * 100),
    }
