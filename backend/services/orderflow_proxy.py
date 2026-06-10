"""
買賣壓代理（Order-Flow Proxy）── Phase 11 step-03
==================================================
免費資料源拿不到真實逐筆 order flow（只有每根 K 棒的「總成交量」）。
這裡用 **tick 規則**近似：用當根相對前一根的漲 / 跌方向，把總量歸給買方或賣方。

⚠️ 誠實標註（很重要，別自欺也別包裝行銷）：
   這是 **tick 代理**（漲跌方向 × 總量），**不是**真實逐筆 order flow。
   真值要付費資料源（Polygon / Databento），列在 Phase 11 範圍外。

設計鐵則（對齊 Phase 6「回測 = 實盤」與護欄合約）：
- **純 pandas、可解釋**：每根算得出來、看得懂。
- **無未來函數**：第 i 根只看自己與前一根（df.iloc[i] 與 df.iloc[i-1]），
  所以對 df.iloc[:i+1] 與完整 df 在第 i 根算出的值一致（與回測 walk-forward 同紀律）。
- **恆等式必須成立**：buy_vol_proxy + sell_vol_proxy == volume（含平盤 / 零量，測試驗）。

平盤（close == prev_close）與第一根（沒有前一根可比）→ **對半分**（買 / 賣各拿一半量）。
對半是唯一能同時「守恆等式」且「方向中性對稱」的選擇；不偏猜某一方。
"""

import numpy as np
import pandas as pd


def compute_orderflow(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    吃一段 K 線 DataFrame（需有 close / volume 欄），回傳「複製一份並加上 4 個買賣壓代理欄」。

    新增欄：
    - buy_vol_proxy  ：當根歸給「買方」的量（漲根 = 全量、跌根 = 0、平盤 / 首根 = 半量）
    - sell_vol_proxy ：當根歸給「賣方」的量（跌根 = 全量、漲根 = 0、平盤 / 首根 = 半量）
    - net_pressure   ：buy_vol_proxy − sell_vol_proxy（>0 偏買、<0 偏賣）
    - pressure_ratio ：buy_vol_proxy ÷ (buy + sell)；無量（分母 0）→ 0.5（中性）

    不改傳入的 df（回傳新物件）。空 df / 缺欄 → 原樣回傳（不崩，上層自理）。
    """
    if price_df is None or price_df.empty or "close" not in price_df or "volume" not in price_df:
        return price_df.copy() if price_df is not None else pd.DataFrame()

    df = price_df.copy()
    close = df["close"]
    volume = df["volume"].astype(float)
    prev_close = close.shift(1)

    is_up = close > prev_close      # 上漲根
    is_down = close < prev_close    # 下跌根
    # 其餘（平盤，或第一根 prev_close 為 NaN）一律對半分

    half = volume / 2.0
    buy = np.where(is_up, volume, np.where(is_down, 0.0, half))
    sell = np.where(is_down, volume, np.where(is_up, 0.0, half))

    df["buy_vol_proxy"] = buy
    df["sell_vol_proxy"] = sell
    df["net_pressure"] = df["buy_vol_proxy"] - df["sell_vol_proxy"]

    total = df["buy_vol_proxy"] + df["sell_vol_proxy"]
    # 分母為 0（無量）時給中性 0.5，避免除以 0 產生 NaN / inf
    df["pressure_ratio"] = np.where(
        total > 0, df["buy_vol_proxy"] / total.where(total > 0, 1.0), 0.5
    )

    return df
