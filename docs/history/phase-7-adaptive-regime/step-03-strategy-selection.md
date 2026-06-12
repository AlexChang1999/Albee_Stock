# 步驟 3 — 狀態 → 策略自適應選擇

> 區塊 2 的收成。這把你的願景「此時此刻該用哪個策略」真正實現。回到 [Phase 7 索引](README.md)。

## 目標

回答：「**現在是 X 狀態，歷史上 X 狀態時哪個策略的 OOS EV 最高？就用它。**」
這就是你說的「A 股爆量滯漲 → 推斷出該用 C 策略」。

## 概念名稱

**自適應策略選擇 / 元策略（Adaptive Strategy Selection / Meta-Strategy）**：
上層不直接交易，而是「挑哪個下層策略來交易」。

## 核心邏輯

1. 把歷史每根 K 棒貼上「當時的狀態標籤」（步驟 2）。
2. 對每個狀態，分別統計「8 個策略在該狀態的子樣本上的 OOS EV / 勝率」。
3. 建一張 **狀態 → 最佳策略對照表（regime→strategy map）**。
4. 實盤時：算當下狀態 → 查表 → 用對應策略產生訊號。

```
狀態                 → 最佳策略（依該狀態 OOS EV）
trending             → donchian / ma_crossover（順勢突破）
ranging              → rsi / bollinger（均值回歸）
high_volume_stall    → （你的例子）可能 momentum 或觀望
high_volatility      → 縮量或不出手
```

## 改動構想

- 新增 `backend/services/strategy_selector.py`：
  - `build_regime_strategy_map(symbol, ...) -> dict`（離線：跑回測 + 狀態標籤 → 算每狀態最佳策略，存 DB 或快取）。
  - `select_strategy(symbol, current_features) -> (strategy_key, params, expected_stats)`（線上：查當下狀態的最佳策略）。
- Bot 可選「固定策略」或「自適應模式」（多一個欄位 `adaptive: bool`，預設關，向後相容）。
- `bot_manager._run_strategy`：`adaptive` 開啟時改走 `select_strategy`。

## 重用現有

- `optimizer.run_auto_backtest`（已能對一檔跑遍所有策略算 EV）——**這正是「每狀態最佳策略」的計算引擎**，只需加一層「依狀態切子樣本」。
- Phase 6 [步驟 4](../phase-6/step-04-out-of-sample-validation.md) 的 **OOS EV**（對照表必須用 OOS，不能用樣本內）。
- `STRATEGY_REGISTRY`（8 個現成策略當候選池）。

## 過擬合風險（這步最危險，務必清醒）

- **切子樣本後每個狀態的樣本數會驟減**——「某狀態只有 12 筆交易、勝率 75%」很可能是運氣。需設**最小樣本門檻**，不足就退回「全樣本最佳策略」或「不出手」。
- 「狀態×策略」的組合數爆炸 = 過擬合自由度爆炸。對照表必須在 OOS 上驗證（步驟 7），且偏好簡單對照（少數狀態、少數策略）。
- **這層的 edge 必須被證明**：若「自適應」在 OOS 上贏不過「單一最佳策略」，就**砍掉這層**（延續不要 vibe slop 原則）。

## 驗收

- `select_strategy` 對「爆量滯漲」狀態回出該狀態歷史 OOS EV 最佳的策略 + 預期勝率。
- 自適應 Bot 在 OOS 回測上的 EV ≥ 同標的單一最佳策略（**否則這層不該存在**）。
- 樣本不足的狀態正確退回保守預設（不亂下注）。
